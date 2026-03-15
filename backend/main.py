from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, Security, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import contextvars
import shutil
import os
import re
import json
import uuid
import filetype
from cachetools import TTLCache

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
    EvalRequest, EvalStatus, EvalMetrics, EvalQuestionResult,
)

# ── Globals ──────────────────────────────────────────────────
INDEX = None
MAX_UPLOAD_MB = settings.max_upload_mb

# In-memory evaluation jobs — {eval_id: dict}
EVAL_JOBS: dict[str, dict] = {}

# Index cache per collection — max 50 entries, TTL 30 min
INDEX_CACHE: TTLCache = TTLCache(maxsize=50, ttl=1800)

# Ingestion status per collection
INGEST_STATUS_BY_COLLECTION: dict[str, dict] = {}

# ContextVar to propagate request_id across async chains
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

def _default_ingest_status(collection: str) -> dict:
    return {
        "status": "idle",
        "message": "No previous ingestion.",
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
    """Validates Bearer token if API_KEY is configured in the environment."""
    api_key = (settings.api_key or "").strip()
    if not api_key:
        return  # Auth disabled if no API_KEY is configured
    if not credentials or credentials.credentials != api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key.")


# ── File validation ──────────────────────────────────────────
ALLOWED_BINARY_MIMES = {"application/pdf", "image/png", "image/jpeg"}
ALLOWED_TEXT_EXTS = {".txt", ".md"}

def validate_upload(content: bytes, filename: str) -> None:
    """Validates actual file size and type via magic bytes (not just extension)."""
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {size_mb:.1f} MB. Maximum: {MAX_UPLOAD_MB} MB."
        )

    ext = Path(filename).suffix.lower()

    if ext in ALLOWED_TEXT_EXTS:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail=f"'{filename}' is not a valid UTF-8 text file."
            )
        return

    kind = filetype.guess(content)
    if kind is None or kind.mime not in ALLOWED_BINARY_MIMES:
        detected = kind.mime if kind else "unknown"
        raise HTTPException(
            status_code=400,
            detail=(
                f"File type not allowed: '{detected}'. "
                "Allowed: PDF, PNG, JPG, TXT, MD."
            ),
        )


# ── Lifespan ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global INDEX
    # settings.google_api_key was already validated by pydantic-settings on startup
    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        existing = {c.name for c in qc.get_collections().collections}
        if settings.collection_name in existing:
            logger.info("Loading existing index from Qdrant...", collection=settings.collection_name)
            INDEX = load_existing_index(settings.collection_name)
            INDEX_CACHE[settings.collection_name] = INDEX
            logger.info("Index loaded OK", collection=settings.collection_name)
        else:
            logger.info("No previous index found. Upload documents and call /ingest.")
    except Exception as e:
        logger.warning("Could not load previous index", error=str(e))
    yield


# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="RAG Multimodal",
    description="Multimodal RAG API with LlamaIndex + Gemini + Qdrant",
    version="1.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Global exception handler ─────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catches unhandled errors and returns structured JSON with error_code."""
    from rag.query import _classify_error
    # If it's a RuntimeError raised by query_rag with an internal JSON payload, parse it
    if isinstance(exc, RuntimeError):
        try:
            payload = json.loads(str(exc))
            if "error_code" in payload:
                return JSONResponse(status_code=500, content=payload)
        except (json.JSONDecodeError, TypeError):
            pass
    # For HTTPException let FastAPI handle them normally
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    error_code, user_msg, suggestion = _classify_error(exc)
    logger.error("Unhandled exception", error_code=error_code, path=str(request.url), error=str(exc))
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


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Generates a UUID4 per request, propagates it via ContextVar and exposes it in the response."""
    request_id = str(uuid.uuid4())
    _request_id_ctx.set(request_id)
    request.state.request_id = request_id
    with logger.contextualize(request_id=request_id):
        response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "index_loaded": INDEX is not None}


@app.post("/upload")
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    collection: str = Query(default=None, description="Target collection name."),
    _: None = Security(verify_api_key),
):
    """Uploads a file to the data directory of the specified collection."""
    col = collection or settings.collection_name
    allowed_exts = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Extension not allowed: '{ext}'. Allowed: {sorted(allowed_exts)}"
        )

    content = await file.read()
    validate_upload(content, file.filename)

    data_dir = get_collection_data_dir(col)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / file.filename).write_bytes(content)

    return {"message": f"File '{file.filename}' uploaded to collection '{col}'. Call /ingest to process."}


@app.get("/documents")
def list_documents(
    collection: str = Query(default=None, description="Collection name."),
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
    collection: str = Query(default=None, description="Collection to ingest."),
    _: None = Security(verify_api_key),
):
    """Triggers ingestion in the background for the specified collection."""
    col = collection or settings.collection_name
    status = INGEST_STATUS_BY_COLLECTION.get(col, _default_ingest_status(col))

    if status["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Ingestion already in progress for '{col}'. Wait for it to finish."
        )

    _data_dir = get_collection_data_dir(col)
    _allowed_doc_exts = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}
    _total = sum(
        1 for f in _data_dir.iterdir()
        if f.is_file() and f.suffix.lower() in _allowed_doc_exts
    ) if _data_dir.exists() else 0
    INGEST_STATUS_BY_COLLECTION[col] = {
        "status": "running",
        "message": "Processing documents...",
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
                "message": "Ingestion completed successfully.",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "processed_docs": INGEST_STATUS_BY_COLLECTION[collection_name].get("total_docs", 0),
            })
            logger.info("Ingestion completed", collection=collection_name)
        except Exception as e:
            INGEST_STATUS_BY_COLLECTION[collection_name].update({
                "status": "failed",
                "message": str(e),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.error("Ingestion error", error=str(e), collection=collection_name, exc_info=True)

    background_tasks.add_task(_run_ingest, col)
    return {"message": f"Ingestion started for '{col}'. Check GET /ingest/status."}


@app.get("/ingest/status", response_model=IngestStatus)
def ingest_status(
    collection: str = Query(default=None, description="Collection to query."),
):
    """Current ingestion status for the specified collection."""
    col = collection or settings.collection_name
    return INGEST_STATUS_BY_COLLECTION.get(col, _default_ingest_status(col))


def _resolve_index(collection: str | None = None):
    """Returns the index for a collection. Uses cache; lazily loads if new."""
    col = collection or settings.collection_name
    if col in INDEX_CACHE:
        return INDEX_CACHE[col]
    if col == settings.collection_name and INDEX is not None:
        return INDEX
    # Lazy load for additional collections
    try:
        idx = load_index_for_collection(col)
        if idx is None:
            return None  # collection does not exist in Qdrant — do not cache
        INDEX_CACHE[col] = idx
        return idx
    except Exception as e:
        logger.error("Could not load index", collection=col, error=str(e))
        return None


@app.post("/query", response_model=QueryResponse)
@limiter.limit("20/minute")
async def query(
    request: Request,
    payload: QueryRequest,
    collection: str | None = Query(default=None),
):
    """RAG query with the user's question. `collection` is optional."""
    idx = _resolve_index(collection)
    if idx is None:
        raise HTTPException(
            status_code=503,
            detail="Collection has no index. Upload documents and call /ingest first.",
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
        # query_rag raises RuntimeError with internal JSON for classified errors
        try:
            payload_err = json.loads(str(exc))
            return JSONResponse(status_code=502, content=payload_err)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=500, detail=str(exc))
    return QueryResponse(**result)


@app.get("/collections", response_model=CollectionsResponse)
def list_collections():
    """Lists all available collections with statistics."""
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
    """Creates a new empty collection in Qdrant with its data directory."""
    try:
        create_collection(payload.name, payload.description)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("Error creating collection", name=payload.name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": f"Collection '{payload.name}' created successfully."}


@app.delete("/collections/{name}")
def delete_named_collection(
    name: str,
    _: None = Security(verify_api_key),
):
    """Deletes a specific collection with all its data and vectors."""
    # Validate name to prevent path traversal
    if not re.match(r'^[a-z0-9][a-z0-9_\-]*$', name):
        raise HTTPException(status_code=400, detail="Invalid collection name.")
    try:
        delete_collection(name)
    except Exception as e:
        logger.error("Error deleting collection", name=name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    # Clear in-memory cache
    INDEX_CACHE.pop(name, None)
    INGEST_STATUS_BY_COLLECTION.pop(name, None)
    global INDEX
    if name == settings.collection_name:
        INDEX = None

    return {"message": f"Collection '{name}' deleted successfully."}


@app.delete("/collection")
def reset_collection(_: None = Security(verify_api_key)):
    """Deletes and recreates the default collection (full reset — compatibility)."""
    return delete_named_collection(settings.collection_name, _)


# ── Delete individual document ────────────────────────────────
@app.delete("/documents/{filename}")
async def delete_document(
    filename: str,
    collection: str = Query(default=None, description="Document collection."),
    _: None = Security(verify_api_key),
):
    """Deletes an individual document from the collection and its vectors from Qdrant."""
    col = collection or settings.collection_name
    data_dir = get_collection_data_dir(col)

    # Security: pathlib ensures the file is inside data_dir (anti path traversal)
    try:
        file_path = (data_dir / filename).resolve()
        file_path.relative_to(data_dir.resolve())
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    deleted_file = False
    if file_path.exists() and file_path.is_file():
        file_path.unlink()
        deleted_file = True

    # Delete vectors from Qdrant filtering by metadata.file_name
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
        logger.warning("Error deleting vectors from Qdrant", filename=filename, collection=col, error=str(e))

    if not deleted_file:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")
    return {"message": f"Document '{filename}' deleted from '{col}'."}


# ── Chat multi-turn ───────────────────────────────────────────
@app.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    collection: str | None = Query(default=None),
):
    """Multi-turn chat with SSE streaming. Sends tokens incrementally."""
    idx = _resolve_index(collection)
    if idx is None:
        raise HTTPException(
            status_code=503,
            detail="Index not available. Upload documents and call /ingest."
        )
    return EventSourceResponse(
        chat_rag_stream(
            idx,
            payload.session_id,
            payload.message,
            payload.top_k,
            file_type_filter=payload.file_type_filter,
            use_hyde=settings.enable_hyde,
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
    """Multi-turn chat without streaming (fallback)."""
    idx = _resolve_index(collection)
    if idx is None:
        raise HTTPException(
            status_code=503,
            detail="Index not available. Upload documents and call /ingest."
        )
    result = chat_rag(
        idx,
        payload.session_id,
        payload.message,
        payload.top_k,
        file_type_filter=payload.file_type_filter,
        use_hyde=settings.enable_hyde,
    )
    return ChatResponse(**result)


@app.delete("/chat/{session_id}")
def clear_session(session_id: str):
    """Deletes the chat history for a session."""
    cleared = clear_chat_session(session_id)
    return {"message": "Session deleted." if cleared else "Session not found.", "cleared": cleared}


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
    """Reconfigures the LLM and embedding models in LlamaIndex Settings."""
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
    logger.info("LLM reconfigured", llm_model=settings.llm_model, embedding_model=settings.embedding_model)


@app.get("/config")
def get_config():
    """Returns the current configuration (without secrets)."""
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
    """Updates configuration in memory (without restarting)."""
    changed_llm = False
    changed_hyde = False
    for field, value in body.model_dump(exclude_none=True).items():
        if field == "enable_hyde" and getattr(settings, field) != value:
            changed_hyde = True
        setattr(settings, field, value)
        if field in ("llm_model", "embedding_model"):
            changed_llm = True
    if changed_llm:
        reinitialize_llm()
    if changed_hyde:
        # Invalidate chat engines cache — the new HyDE state must apply
        from rag.query import _CHAT_ENGINES
        _CHAT_ENGINES.clear()
        logger.info("Chat engines cache invalidated due to enable_hyde change", enable_hyde=settings.enable_hyde)
    return {"ok": True}


# ── RAG Evaluation ───────────────────────────────────────────

@app.post("/eval", status_code=202)
async def start_evaluation(
    payload: EvalRequest,
    background_tasks: BackgroundTasks,
):
    """Starts a RAG evaluation in the background. Returns eval_id to check status."""
    idx = _resolve_index(payload.collection)
    if idx is None:
        raise HTTPException(
            status_code=503,
            detail="Index not available. Upload documents and call /ingest first.",
        )

    eval_id = str(uuid.uuid4())
    EVAL_JOBS[eval_id] = {
        "eval_id": eval_id,
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_questions": len(payload.questions),
        "top_k": payload.top_k,
        "questions_done": 0,
        "progress": 0,
        "metrics": None,
        "results": None,
        "error": None,
    }

    def _run_eval(eval_id: str, questions, top_k: int, index):
        from rag.eval import evaluate_question, aggregate_metrics
        results = []
        for i, q in enumerate(questions):
            try:
                r = evaluate_question(index, q.question, q.ground_truth, top_k)
                results.append(r)
            except Exception as exc:
                logger.error("Error evaluating question", question=q.question[:80], error=str(exc))
                results.append({
                    "question": q.question,
                    "answer": f"Error: {str(exc)[:200]}",
                    "ground_truth": q.ground_truth,
                    "faithfulness": 0.0,
                    "answer_relevancy": 0.0,
                    "context_recall": 0.0,
                    "context_precision": 0.0,
                    "nodes_retrieved": 0,
                })
            EVAL_JOBS[eval_id].update({
                "questions_done": i + 1,
                "progress": int((i + 1) / len(questions) * 100),
            })

        metrics = aggregate_metrics(results)
        EVAL_JOBS[eval_id].update({
            "status": "done",
            "progress": 100,
            "metrics": metrics,
            "results": results,
        })
        logger.info("Evaluation completed", eval_id=eval_id, n_questions=len(questions))

    background_tasks.add_task(_run_eval, eval_id, payload.questions, payload.top_k, idx)
    return {"eval_id": eval_id, "message": f"Evaluation started with {len(payload.questions)} question(s)."}


@app.get("/eval/{eval_id}", response_model=EvalStatus)
def get_eval_status(eval_id: str):
    """Returns the status and results of an evaluation by its ID."""
    job = EVAL_JOBS.get(eval_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return job


# ── Feedback de calidad ───────────────────────────────────────
FEEDBACK_FILE = Path("./feedback.jsonl")


@app.post("/feedback")
async def submit_feedback(payload: FeedbackRequest):
    """Records quality feedback (thumbs up/down) to a JSONL file."""
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
    return {"message": "Feedback recorded. Thank you!"}
