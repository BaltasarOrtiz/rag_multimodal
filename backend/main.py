from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, Security, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import shutil
import os
import re
import json
import filetype

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sse_starlette.sse import EventSourceResponse

from config import settings
from logger import logger
from rag.ingest import (
    ingest_documents, load_existing_index, load_index_for_collection,
    create_collection, delete_collection, list_all_collections,
    get_collection_data_dir,
)
from rag.query import query_rag, chat_rag, chat_rag_stream, clear_chat_session
from rag.models import (
    QueryRequest, QueryResponse, IngestRequest, IngestStatus,
    ChatRequest, ChatResponse, FeedbackRequest,
    CollectionCreateRequest, CollectionInfo, CollectionsResponse,
)

# ── Globals ──────────────────────────────────────────────────
INDEX = None
MAX_UPLOAD_MB = settings.max_upload_mb

# Cache de índices por colección (múltiples knowledge bases)
INDEX_CACHE: dict[str, object] = {}

# Estado de ingestión por colección
INGEST_STATUS_BY_COLLECTION: dict[str, dict] = {}

def _default_ingest_status(collection: str) -> dict:
    return {
        "status": "idle",
        "message": "Sin ingestión previa.",
        "started_at": None,
        "finished_at": None,
        "collection": collection,
        "total_docs": 0,
        "processed_docs": 0,
    }

# ── Rate Limiter ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Auth (opcional) ──────────────────────────────────────────
_bearer_scheme = HTTPBearer(auto_error=False)

def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme)):
    """Valida Bearer token si API_KEY está configurada en el entorno."""
    api_key = (settings.api_key or "").strip()
    if not api_key:
        return  # Auth desactivada si no hay API_KEY configurada
    if not credentials or credentials.credentials != api_key:
        raise HTTPException(status_code=401, detail="API Key inválida o ausente.")


# ── File validation ──────────────────────────────────────────
ALLOWED_BINARY_MIMES = {"application/pdf", "image/png", "image/jpeg"}
ALLOWED_TEXT_EXTS = {".txt", ".md"}

def validate_upload(content: bytes, filename: str) -> None:
    """Valida tamaño real y tipo de archivo por magic bytes (no solo extensión)."""
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Archivo demasiado grande: {size_mb:.1f} MB. Máximo: {MAX_UPLOAD_MB} MB."
        )

    ext = Path(filename).suffix.lower()

    if ext in ALLOWED_TEXT_EXTS:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail=f"'{filename}' no es un archivo de texto UTF-8 válido."
            )
        return

    kind = filetype.guess(content)
    if kind is None or kind.mime not in ALLOWED_BINARY_MIMES:
        detected = kind.mime if kind else "desconocido"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Tipo de archivo no permitido: '{detected}'. "
                "Permitidos: PDF, PNG, JPG, TXT, MD."
            ),
        )


# ── Lifespan ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global INDEX
    # settings.google_api_key ya fue validado por pydantic-settings al arrancar
    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        existing = {c.name for c in qc.get_collections().collections}
        if settings.collection_name in existing:
            logger.info("Cargando index existente desde Qdrant...", collection=settings.collection_name)
            INDEX = load_existing_index(settings.collection_name)
            INDEX_CACHE[settings.collection_name] = INDEX
            logger.info("Index cargado OK", collection=settings.collection_name)
        else:
            logger.info("No hay index previo. Sube documentos y llama /ingest.")
    except Exception as e:
        logger.warning("No se pudo cargar index previo", error=str(e))
    yield


# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="RAG Multimodal",
    description="API RAG Multimodal con LlamaIndex + Gemini + Qdrant",
    version="1.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Global exception handler ─────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Captura errores no controlados y devuelve JSON estructurado con error_code."""
    from rag.query import _classify_error
    # Si es un RuntimeError lanzado por query_rag con JSON interno, lo parseamos
    if isinstance(exc, RuntimeError):
        try:
            payload = json.loads(str(exc))
            if "error_code" in payload:
                return JSONResponse(status_code=500, content=payload)
        except (json.JSONDecodeError, TypeError):
            pass
    # Para HTTPException dejamos que FastAPI las maneje normalmente
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    error_code, user_msg, suggestion = _classify_error(exc)
    logger.error("Excepción no controlada", error_code=error_code, path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": user_msg, "error_code": error_code, "suggestion": suggestion},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "index_loaded": INDEX is not None}


@app.post("/upload")
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    collection: str = Query(default=None, description="Nombre de la colección destino."),
    _: None = Security(verify_api_key),
):
    """Sube un archivo al directorio de datos de la colección indicada."""
    col = collection or settings.collection_name
    allowed_exts = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Extensión no permitida: '{ext}'. Permitidas: {sorted(allowed_exts)}"
        )

    content = await file.read()
    validate_upload(content, file.filename)

    data_dir = get_collection_data_dir(col)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / file.filename).write_bytes(content)

    return {"message": f"Archivo '{file.filename}' subido a colección '{col}'. Llama /ingest para procesar."}


@app.get("/documents")
def list_documents(
    collection: str = Query(default=None, description="Nombre de la colección."),
):
    col = collection or settings.collection_name
    data_dir = get_collection_data_dir(col)
    data_dir.mkdir(parents=True, exist_ok=True)
    files = [
        {"name": f.name, "size": f.stat().st_size, "ext": f.suffix}
        for f in data_dir.iterdir()
        if f.is_file() and f.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}
    ]
    return {"documents": files, "total": len(files), "collection": col}


@app.post("/ingest")
@limiter.limit("5/minute")
async def ingest(
    request: Request,
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    collection: str = Query(default=None, description="Colección a ingestar."),
    _: None = Security(verify_api_key),
):
    """Dispara la ingestión en background para la colección indicada."""
    col = collection or settings.collection_name
    status = INGEST_STATUS_BY_COLLECTION.get(col, _default_ingest_status(col))

    if status["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Ya hay una ingestión en curso para '{col}'. Espera a que termine."
        )

    _data_dir = get_collection_data_dir(col)
    _allowed_doc_exts = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}
    _total = sum(
        1 for f in _data_dir.iterdir()
        if f.is_file() and f.suffix.lower() in _allowed_doc_exts
    ) if _data_dir.exists() else 0
    INGEST_STATUS_BY_COLLECTION[col] = {
        "status": "running",
        "message": "Procesando documentos...",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "collection": col,
        "total_docs": _total,
        "processed_docs": 0,
    }

    def _run_ingest(collection_name: str):
        global INDEX
        try:
            idx = ingest_documents(collection_name)
            INDEX_CACHE[collection_name] = idx
            if collection_name == settings.collection_name:
                INDEX = idx
            INGEST_STATUS_BY_COLLECTION[collection_name].update({
                "status": "done",
                "message": "Ingestión completada exitosamente.",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "processed_docs": INGEST_STATUS_BY_COLLECTION[collection_name].get("total_docs", 0),
            })
            logger.info("Ingestión completada", collection=collection_name)
        except Exception as e:
            INGEST_STATUS_BY_COLLECTION[collection_name].update({
                "status": "failed",
                "message": str(e),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.error("Error en ingestión", error=str(e), collection=collection_name, exc_info=True)

    background_tasks.add_task(_run_ingest, col)
    return {"message": f"Ingestión iniciada para '{col}'. Consulta GET /ingest/status."}


@app.get("/ingest/status", response_model=IngestStatus)
def ingest_status(
    collection: str = Query(default=None, description="Colección a consultar."),
):
    """Estado actual de la ingestión para la colección indicada."""
    col = collection or settings.collection_name
    return INGEST_STATUS_BY_COLLECTION.get(col, _default_ingest_status(col))


def _resolve_index(collection: str | None = None):
    """Retorna el índice para una colección. Usa cache; carga perezosamente si es nueva."""
    col = collection or settings.collection_name
    if col in INDEX_CACHE:
        return INDEX_CACHE[col]
    if col == settings.collection_name and INDEX is not None:
        return INDEX
    # Carga perezosa para colecciones adicionales
    try:
        idx = load_index_for_collection(col)
        if idx is None:
            return None  # colección no existe en Qdrant — no cachear
        INDEX_CACHE[col] = idx
        return idx
    except Exception as e:
        logger.error("No se pudo cargar índice", collection=col, error=str(e))
        return None


@app.post("/query", response_model=QueryResponse)
@limiter.limit("20/minute")
async def query(
    request: Request,
    payload: QueryRequest,
    collection: str | None = Query(default=None),
):
    """Consulta RAG con la pregunta del usuario. `collection` es opcional."""
    idx = _resolve_index(collection)
    if idx is None:
        raise HTTPException(
            status_code=503,
            detail="Colección sin índice. Sube documentos y llama /ingest primero.",
        )
    try:
        result = query_rag(
            idx,
            payload.query,
            payload.top_k,
            file_type_filter=payload.file_type_filter,
            use_hyde=payload.use_hyde,
        )
    except RuntimeError as exc:
        # query_rag lanza RuntimeError con JSON interno para errores clasificados
        try:
            payload_err = json.loads(str(exc))
            return JSONResponse(status_code=502, content=payload_err)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=500, detail=str(exc))
    return QueryResponse(**result)


@app.get("/collections", response_model=CollectionsResponse)
def list_collections():
    """Lista todas las colecciones disponibles con estadísticas."""
    cols = list_all_collections()
    return CollectionsResponse(
        collections=[CollectionInfo(**c) for c in cols],
        active=settings.collection_name,
    )


@app.post("/collections", status_code=201)
def create_new_collection(
    payload: CollectionCreateRequest,
    _: None = Security(verify_api_key),
):
    """Crea una nueva colección vacía en Qdrant con su directorio de datos."""
    try:
        create_collection(payload.name, payload.description)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("Error al crear colección", name=payload.name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": f"Colección '{payload.name}' creada exitosamente."}


@app.delete("/collections/{name}")
def delete_named_collection(
    name: str,
    _: None = Security(verify_api_key),
):
    """Elimina una colección específica con todos sus datos y vectores."""
    # Validar nombre para prevenir path traversal
    if not re.match(r'^[a-z0-9][a-z0-9_\-]*$', name):
        raise HTTPException(status_code=400, detail="Nombre de colección inválido.")
    try:
        delete_collection(name)
    except Exception as e:
        logger.error("Error al eliminar colección", name=name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    # Limpiar cache en memoria
    INDEX_CACHE.pop(name, None)
    INGEST_STATUS_BY_COLLECTION.pop(name, None)
    global INDEX
    if name == settings.collection_name:
        INDEX = None

    return {"message": f"Colección '{name}' eliminada correctamente."}


@app.delete("/collection")
def reset_collection(_: None = Security(verify_api_key)):
    """Elimina y recrea la colección por defecto (reset total — compatibilidad)."""
    return delete_named_collection(settings.collection_name, _)


# ── Delete individual document ────────────────────────────────
@app.delete("/documents/{filename}")
async def delete_document(
    filename: str,
    collection: str = Query(default=None, description="Colección del documento."),
    _: None = Security(verify_api_key),
):
    """Elimina un documento individual de la colección y sus vectores de Qdrant."""
    col = collection or settings.collection_name
    data_dir = get_collection_data_dir(col)

    # Security: pathlib garantiza que el archivo esté dentro de data_dir (anti path traversal)
    try:
        file_path = (data_dir / filename).resolve()
        file_path.relative_to(data_dir.resolve())
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido.")
    deleted_file = False
    if file_path.exists() and file_path.is_file():
        file_path.unlink()
        deleted_file = True

    # Eliminar vectores de Qdrant filtrando por metadata.file_name
    try:
        from rag.ingest import get_qdrant_client
        from qdrant_client.models import FilterSelector, Filter, FieldCondition, MatchValue
        client = get_qdrant_client()
        client.delete(
            collection_name=col,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="file_name", match=MatchValue(value=filename))]
                )
            ),
        )
    except Exception as e:
        logger.warning("Error al eliminar vectores de Qdrant", filename=filename, collection=col, error=str(e))

    if not deleted_file:
        raise HTTPException(status_code=404, detail=f"Documento '{filename}' no encontrado.")
    return {"message": f"Documento '{filename}' eliminado de '{col}'."}


# ── Chat multi-turn ───────────────────────────────────────────
@app.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    collection: str | None = Query(default=None),
):
    """Chat multi-turn con streaming SSE. Envía tokens incrementalmente."""
    idx = _resolve_index(collection)
    if idx is None:
        raise HTTPException(
            status_code=503,
            detail="Index no disponible. Sube documentos y llama /ingest."
        )
    return EventSourceResponse(
        chat_rag_stream(
            idx,
            payload.session_id,
            payload.message,
            payload.top_k,
            file_type_filter=payload.file_type_filter,
        ),
        sep="\n",
    )


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    payload: ChatRequest,
    collection: str | None = Query(default=None),
):
    """Chat multi-turn sin streaming (fallback)."""
    idx = _resolve_index(collection)
    if idx is None:
        raise HTTPException(
            status_code=503,
            detail="Index no disponible. Sube documentos y llama /ingest."
        )
    result = chat_rag(
        idx,
        payload.session_id,
        payload.message,
        payload.top_k,
        file_type_filter=payload.file_type_filter,
    )
    return ChatResponse(**result)


@app.delete("/chat/{session_id}")
def clear_session(session_id: str):
    """Elimina el historial de chat de una sesión."""
    cleared = clear_chat_session(session_id)
    return {"message": "Sesión eliminada." if cleared else "Sesión no encontrada.", "cleared": cleared}


# ── Config endpoints ─────────────────────────────────────────

class ConfigUpdate(BaseModel):
    llm_model: str | None = None
    embedding_model: str | None = None
    enable_hybrid: bool | None = None
    enable_reranker: bool | None = None
    enable_hyde: bool | None = None
    enable_semantic_chunking: bool | None = None
    reranker_model: str | None = None
    hybrid_alpha: float | None = None


def reinitialize_llm():
    """Reconfigura los modelos LLM y embedding en LlamaIndex Settings."""
    from llama_index.core import Settings as LlamaSettings
    from llama_index.llms.google_genai import GoogleGenAI
    from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
    LlamaSettings.llm = GoogleGenAI(
        model=settings.llm_model,
        api_key=settings.google_api_key,
    )
    LlamaSettings.embed_model = GoogleGenAIEmbedding(
        model_name=settings.embedding_model,
        api_key=settings.google_api_key,
    )
    logger.info("LLM reconfigurado", llm_model=settings.llm_model, embedding_model=settings.embedding_model)


@app.get("/config")
def get_config():
    """Retorna la configuración actual (sin secretos)."""
    return {
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "enable_hybrid": settings.enable_hybrid,
        "enable_reranker": settings.enable_reranker,
        "enable_hyde": settings.enable_hyde,
        "enable_semantic_chunking": settings.enable_semantic_chunking,
        "reranker_model": settings.reranker_model,
        "hybrid_alpha": settings.hybrid_alpha,
        "embedding_dim": settings.embedding_dim,
    }


@app.put("/config")
async def update_config(body: ConfigUpdate, _: None = Security(verify_api_key)):
    """Actualiza la configuración en memoria (sin reiniciar)."""
    changed_llm = False
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(settings, field, value)
        if field in ("llm_model", "embedding_model"):
            changed_llm = True
    if changed_llm:
        reinitialize_llm()
    return {"ok": True}


# ── Feedback de calidad ───────────────────────────────────────
FEEDBACK_FILE = Path("./feedback.jsonl")


@app.post("/feedback")
async def submit_feedback(payload: FeedbackRequest):
    """Registra feedback de calidad (thumbs up/down) en un archivo JSONL."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "query_id": payload.query_id,
        "query": payload.query,
        "answer": payload.answer[:300],
        "rating": payload.rating,
        "comment": payload.comment,
    }
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"message": "Feedback registrado. ¡Gracias!"}
