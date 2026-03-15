import asyncio
import json
import threading
import uuid
from typing import AsyncGenerator, Optional
from cachetools import TTLCache

from llama_index.core import VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.vector_stores.types import (
    MetadataFilter,
    MetadataFilters,
    VectorStoreQueryMode,
)
from llama_index.core.indices.query.query_transform import HyDEQueryTransform
from llama_index.core.query_engine import TransformQueryEngine
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.chat_engine import CondensePlusContextChatEngine

from config import settings as app_settings
from rag.models import SourceInfo


# ── HyDE Retriever wrapper ────────────────────────────────────
class _HyDERetriever(BaseRetriever):
    """Wrapper que aplica HyDEQueryTransform antes de recuperar nodos.
    Permite usar HyDE en chat engines (CondensePlusContextChatEngine),
    donde el TransformQueryEngine no aplica directamente.
    """
    def __init__(self, base_retriever: BaseRetriever) -> None:
        self._base = base_retriever
        self._hyde = HyDEQueryTransform(include_original=True)
        super().__init__()

    def _retrieve(self, query_bundle):
        transformed = self._hyde(query_bundle)
        return self._base.retrieve(transformed)


# ── Error classification ──────────────────────────────────────
def _classify_error(exc: Exception) -> tuple[str, str, str]:
    """
    Clasifica una excepción y retorna (error_code, mensaje_usuario, sugerencia).

    Códigos de error:
      qdrant_not_found   — colección inexistente (404)
      qdrant_unavailable — Qdrant inaccesible (502/503)
      qdrant_error       — otros errores de Qdrant
      llm_quota          — cuota de Google API agotada
      llm_auth           — credencial de Google inválida
      llm_unavailable    — API de Gemini inaccesible
      llm_timeout        — Gemini superó el tiempo de espera
      llm_error          — otros errores del LLM
      hybrid_config      — colección sin sparse vectors para modo híbrido
      connection_error   — error de red entre servicios
      timeout            — timeout genérico
      unknown            — error no clasificado
    """
    exc_str = str(exc).lower()

    # ── Qdrant ────────────────────────────────────────────────
    try:
        from qdrant_client.http.exceptions import UnexpectedResponse
        if isinstance(exc, UnexpectedResponse):
            code = getattr(exc, "status_code", 0)
            if code == 404:
                return (
                    "qdrant_not_found",
                    "La colección no existe en Qdrant.",
                    "Ingesta documentos primero con el botón 'Ingestar'.",
                )
            if code in (502, 503, 500):
                return (
                    "qdrant_unavailable",
                    f"Qdrant no responde (HTTP {code}).",
                    "Verifica que el servicio Qdrant esté corriendo.",
                )
            return (
                "qdrant_error",
                f"Error de Qdrant (HTTP {code}): {str(exc)[:120]}",
                "Revisa los logs del contenedor Qdrant.",
            )
    except ImportError:
        pass

    if "connection refused" in exc_str and ("6333" in exc_str or "qdrant" in exc_str):
        return (
            "qdrant_unavailable",
            "No se puede conectar a Qdrant.",
            "Verifica que el contenedor 'qdrant' esté en ejecución.",
        )

    # ── LlamaIndex config ─────────────────────────────────────
    if "hybrid search is not enabled" in exc_str:
        return (
            "hybrid_config",
            "La colección no tiene vectores sparse para búsqueda híbrida.",
            "Re-ingesta los documentos para activar el modo híbrido.",
        )

    # ── Google API ────────────────────────────────────────────
    try:
        from google.api_core.exceptions import (
            ResourceExhausted, PermissionDenied, Unauthenticated,
            ServiceUnavailable, DeadlineExceeded, GoogleAPICallError,
        )
        if isinstance(exc, ResourceExhausted):
            return (
                "llm_quota",
                "Cuota de Google API agotada (429).",
                "Espera unos minutos o revisa los límites de tu proyecto en Google AI Studio.",
            )
        if isinstance(exc, (PermissionDenied, Unauthenticated)):
            return (
                "llm_auth",
                "Credencial de Google API inválida o sin permisos.",
                "Verifica que GOOGLE_API_KEY sea correcta y tenga acceso a Gemini.",
            )
        if isinstance(exc, ServiceUnavailable):
            return (
                "llm_unavailable",
                "La API de Google Gemini no está disponible.",
                "Intenta de nuevo en unos segundos.",
            )
        if isinstance(exc, DeadlineExceeded):
            return (
                "llm_timeout",
                "La consulta a Gemini superó el tiempo límite.",
                "Prueba reducir Top-K o usar un mensaje más corto.",
            )
        if isinstance(exc, GoogleAPICallError):
            return (
                "llm_error",
                f"Error de Google API: {str(exc)[:120]}",
                "Revisa el estado de la API en https://status.cloud.google.com",
            )
    except ImportError:
        pass

    # ── Genéricos ─────────────────────────────────────────────
    if "rate limit" in exc_str or "quota" in exc_str or "429" in exc_str:
        return (
            "llm_quota",
            "Límite de peticiones alcanzado.",
            "Espera unos segundos antes de enviar otra consulta.",
        )
    if isinstance(exc, TimeoutError) or "timeout" in exc_str:
        return (
            "timeout",
            "La operación excedió el tiempo de espera.",
            "Prueba con un Top-K menor o un mensaje más corto.",
        )
    if isinstance(exc, ConnectionError) or "connection" in exc_str:
        return (
            "connection_error",
            "Error de conexión con un servicio externo.",
            "Verifica la conectividad entre los contenedores Docker.",
        )

    return (
        "unknown",
        f"Error inesperado ({type(exc).__name__}): {str(exc)[:200]}",
        "Revisa los logs del servidor para más detalles.",
    )

# ── Reranker singleton ────────────────────────────────────────
_reranker: Optional[SentenceTransformerRerank] = None
_reranker_lock = threading.Lock()


def _get_reranker(top_n: int) -> Optional[SentenceTransformerRerank]:
    """Carga el cross-encoder la primera vez y reutiliza la instancia."""
    global _reranker
    if not app_settings.enable_reranker:
        return None
    with _reranker_lock:
        if _reranker is None:
            try:
                _reranker = SentenceTransformerRerank(model=app_settings.reranker_model, top_n=top_n)
                print(f"✅ Reranker cargado: {app_settings.reranker_model}")
            except Exception as exc:
                print(f"⚠️  Reranker no disponible ({exc}). Usando ranking por coseno.")
                return None
        else:
            _reranker.top_n = top_n
        return _reranker


# ── Chat Engine Registry — máx 50 sesiones, TTL 30 min ────────
_CHAT_ENGINES: TTLCache = TTLCache(maxsize=50, ttl=1800)


def _effective_query_mode(index: VectorStoreIndex) -> VectorStoreQueryMode:
    """Determina el modo real según el QdrantVectorStore subyacente del índice.

    Aunque ENABLE_HYBRID=true en settings, el store puede ser dense-only si
    la colección fue creada sin sparse vectors (p.ej. colección antigua o vacía).
    Consultar el atributo _enable_hybrid del store evita el ValueError de LlamaIndex.
    """
    if not app_settings.enable_hybrid:
        return VectorStoreQueryMode.DEFAULT
    vs = getattr(index, '_vector_store', None)
    if vs is not None and getattr(vs, '_enable_hybrid', False):
        return VectorStoreQueryMode.HYBRID
    return VectorStoreQueryMode.DEFAULT


def get_or_create_chat_engine(
    index: VectorStoreIndex,
    session_id: str,
    top_k: int = 3,
    metadata_filters: Optional[MetadataFilters] = None,
    use_hyde: bool = False,
):
    """Obtiene o crea un chat engine con memoria, reranking y HyDE opcional."""
    apply_hyde = use_hyde or app_settings.enable_hyde
    cache_key = f"{session_id}:{top_k}:{apply_hyde}"
    if cache_key not in _CHAT_ENGINES:
        postprocessors = []
        reranker = _get_reranker(top_n=top_k)
        if reranker:
            postprocessors.append(reranker)

        effective_mode = _effective_query_mode(index)
        similarity_top_k = top_k * 3 if reranker else top_k

        retriever_kwargs: dict = dict(
            similarity_top_k=similarity_top_k,
            vector_store_query_mode=effective_mode,
        )
        if effective_mode == VectorStoreQueryMode.HYBRID:
            retriever_kwargs["alpha"] = app_settings.hybrid_alpha
        if metadata_filters:
            retriever_kwargs["filters"] = metadata_filters

        base_retriever = index.as_retriever(**retriever_kwargs)

        if apply_hyde:
            try:
                retriever = _HyDERetriever(base_retriever)
                print("🔮 HyDE activado para chat engine")
            except Exception as exc:
                print(f"⚠️  HyDE no disponible para chat ({exc}). Usando retriever estándar.")
                retriever = base_retriever
        else:
            retriever = base_retriever

        _CHAT_ENGINES[cache_key] = CondensePlusContextChatEngine.from_defaults(
            retriever=retriever,
            memory=ChatMemoryBuffer.from_defaults(token_limit=4096),
            node_postprocessors=postprocessors,
        )
    return _CHAT_ENGINES[cache_key]


def clear_chat_session(session_id: str) -> bool:
    """Elimina todos los engines de chat vinculados a la sesión."""
    removed = [k for k in list(_CHAT_ENGINES) if k.startswith(f"{session_id}:")]
    for k in removed:
        del _CHAT_ENGINES[k]
    return bool(removed)


def _nodes_to_sources(nodes) -> list[SourceInfo]:
    return [
        SourceInfo(
            filename=node.metadata.get("file_name") or node.metadata.get("source", "desconocido"),
            text=(node.text or "")[:600],
            score=round(float(node.score or 0.0), 4),
        )
        for node in (nodes or [])
    ]


def _build_filters(file_type: Optional[str]) -> Optional[MetadataFilters]:
    """Construye MetadataFilters opcionales a partir de parámetros de query."""
    if not file_type:
        return None
    return MetadataFilters(
        filters=[MetadataFilter(key="file_type", value=file_type.lower())]
    )


def query_rag(
    index: VectorStoreIndex,
    query: str,
    top_k: int = 3,
    file_type_filter: Optional[str] = None,
    use_hyde: bool = False,
) -> dict:
    """
    Consulta RAG de turno único con búsqueda híbrida y reranking opcional.

    - file_type_filter: filtrar por extensión ('.pdf', '.txt', etc.)
    - use_hyde: aplicar HyDE (Hypothetical Document Embeddings) antes de buscar
    """
    postprocessors = []
    reranker = _get_reranker(top_n=top_k)
    if reranker:
        postprocessors.append(reranker)

    effective_mode = _effective_query_mode(index)
    engine_kwargs: dict = dict(
        similarity_top_k=top_k * 3 if reranker else top_k,
        vector_store_query_mode=effective_mode,
        response_mode="compact",
        node_postprocessors=postprocessors,
    )
    if effective_mode == VectorStoreQueryMode.HYBRID:
        engine_kwargs["alpha"] = app_settings.hybrid_alpha
    filters = _build_filters(file_type_filter)
    if filters:
        engine_kwargs["filters"] = filters

    base_engine = index.as_query_engine(**engine_kwargs)

    # HyDE: generar documento hipotético antes de buscar
    apply_hyde = use_hyde or app_settings.enable_hyde
    engine = base_engine
    if apply_hyde:
        try:
            hyde_transform = HyDEQueryTransform(include_original=True)
            engine = TransformQueryEngine(base_engine, query_transform=hyde_transform)
        except Exception as exc:
            print(f"⚠️  HyDE no disponible ({exc}). Usando query sin transformación.")

    try:
        response = engine.query(query)
    except Exception as exc:
        error_code, user_msg, suggestion = _classify_error(exc)
        print(f"[query_rag] {error_code}: {exc}")
        raise RuntimeError(json.dumps({
            "detail": user_msg,
            "error_code": error_code,
            "suggestion": suggestion,
        })) from exc
    return {
        "answer": str(response),
        "sources": _nodes_to_sources(response.source_nodes),
        "nodes_retrieved": len(response.source_nodes),
    }


async def chat_rag_stream(
    index: VectorStoreIndex,
    session_id: str,
    message: str,
    top_k: int = 3,
    file_type_filter: Optional[str] = None,
    use_hyde: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    Genera eventos SSE para el chat multi-turn con reranking y HyDE opcional.
    Envía tokens con event='token' y al final sources con event='sources'.
    """
    loop = asyncio.get_event_loop()
    filters = _build_filters(file_type_filter)
    engine = get_or_create_chat_engine(index, session_id, top_k, metadata_filters=filters, use_hyde=use_hyde)
    try:
        streaming_resp = await loop.run_in_executor(None, engine.stream_chat, message)
    except Exception as exc:
        error_code, user_msg, suggestion = _classify_error(exc)
        print(f"[chat_rag_stream] {error_code}: {exc}")
        yield {
            "event": "error",
            "data": json.dumps({
                "detail": user_msg,
                "error_code": error_code,
                "suggestion": suggestion,
            }),
        }
        return

    try:
        for token in streaming_resp.response_gen:
            yield {"event": "token", "data": token}
            await asyncio.sleep(0)
    except Exception as exc:
        error_code, user_msg, suggestion = _classify_error(exc)
        print(f"[chat_rag_stream/tokens] {error_code}: {exc}")
        yield {
            "event": "error",
            "data": json.dumps({
                "detail": user_msg,
                "error_code": error_code,
                "suggestion": suggestion,
            }),
        }
        return

    source_nodes = getattr(streaming_resp, "source_nodes", None) or []
    sources = [s.model_dump() for s in _nodes_to_sources(source_nodes)]
    yield {
        "event": "sources",
        "data": json.dumps({
            "sources": sources,
            "nodes_retrieved": len(source_nodes),
            "query_id": str(uuid.uuid4()),
            "session_id": session_id,
        }),
    }


def chat_rag(
    index: VectorStoreIndex,
    session_id: str,
    message: str,
    top_k: int = 3,
    file_type_filter: Optional[str] = None,
    use_hyde: bool = False,
) -> dict:
    """Chat multi-turn sin streaming (fallback)."""
    filters = _build_filters(file_type_filter)
    engine = get_or_create_chat_engine(index, session_id, top_k, metadata_filters=filters, use_hyde=use_hyde)
    response = engine.chat(message)
    source_nodes = getattr(response, "source_nodes", None) or []
    return {
        "answer": str(response),
        "sources": _nodes_to_sources(source_nodes),
        "nodes_retrieved": len(source_nodes),
        "session_id": session_id,
    }
