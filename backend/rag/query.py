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
    """Wrapper that applies HyDEQueryTransform before retrieving nodes.
    Allows using HyDE in chat engines (CondensePlusContextChatEngine),
    where TransformQueryEngine does not apply directly.
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
    Classifies an exception and returns (error_code, user_message, suggestion).

    Error codes:
      qdrant_not_found   — non-existent collection (404)
      qdrant_unavailable — Qdrant unreachable (502/503)
      qdrant_error       — other Qdrant errors
      llm_quota          — Google API quota exhausted
      llm_auth           — invalid Google credential
      llm_unavailable    — Gemini API unreachable
      llm_timeout        — Gemini exceeded the wait time
      llm_error          — other LLM errors
      hybrid_config      — collection without sparse vectors for hybrid mode
      connection_error   — network error between services
      timeout            — generic timeout
      unknown            — unclassified error
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
                    "The collection does not exist in Qdrant.",
                    "Ingest documents first using the 'Ingest' button.",
                )
            if code in (502, 503, 500):
                return (
                    "qdrant_unavailable",
                    f"Qdrant is not responding (HTTP {code}).",
                    "Verify that the Qdrant service is running.",
                )
            return (
                "qdrant_error",
                f"Qdrant error (HTTP {code}): {str(exc)[:120]}",
                "Check the Qdrant container logs.",
            )
    except ImportError:
        pass

    if "connection refused" in exc_str and ("6333" in exc_str or "qdrant" in exc_str):
        return (
            "qdrant_unavailable",
            "Cannot connect to Qdrant.",
            "Verify that the 'qdrant' container is running.",
        )

    # ── LlamaIndex config ─────────────────────────────────────
    if "hybrid search is not enabled" in exc_str:
        return (
            "hybrid_config",
            "The collection has no sparse vectors for hybrid search.",
            "Re-ingest the documents to activate hybrid mode.",
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
                "Google API quota exhausted (429).",
                "Wait a few minutes or check the limits for your project in Google AI Studio.",
            )
        if isinstance(exc, (PermissionDenied, Unauthenticated)):
            return (
                "llm_auth",
                "Invalid Google API credential or insufficient permissions.",
                "Verify that GOOGLE_API_KEY is correct and has access to Gemini.",
            )
        if isinstance(exc, ServiceUnavailable):
            return (
                "llm_unavailable",
                "The Google Gemini API is not available.",
                "Try again in a few seconds.",
            )
        if isinstance(exc, DeadlineExceeded):
            return (
                "llm_timeout",
                "The Gemini query exceeded the time limit.",
                "Try reducing Top-K or using a shorter message.",
            )
        if isinstance(exc, GoogleAPICallError):
            return (
                "llm_error",
                f"Google API error: {str(exc)[:120]}",
                "Check the API status at https://status.cloud.google.com",
            )
    except ImportError:
        pass

    # ── Generic ───────────────────────────────────────────────
    if "rate limit" in exc_str or "quota" in exc_str or "429" in exc_str:
        return (
            "llm_quota",
            "Request rate limit reached.",
            "Wait a few seconds before sending another query.",
        )
    if isinstance(exc, TimeoutError) or "timeout" in exc_str:
        return (
            "timeout",
            "The operation exceeded the wait time.",
            "Try a lower Top-K or a shorter message.",
        )
    if isinstance(exc, ConnectionError) or "connection" in exc_str:
        return (
            "connection_error",
            "Connection error with an external service.",
            "Verify connectivity between Docker containers.",
        )

    return (
        "unknown",
        f"Unexpected error ({type(exc).__name__}): {str(exc)[:200]}",
        "Check the server logs for more details.",
    )

# ── Reranker singleton ────────────────────────────────────────
_reranker: Optional[SentenceTransformerRerank] = None
_reranker_lock = threading.Lock()


def _get_reranker(top_n: int) -> Optional[SentenceTransformerRerank]:
    """Loads the cross-encoder on first use and reuses the instance."""
    global _reranker
    if not app_settings.enable_reranker:
        return None
    with _reranker_lock:
        if _reranker is None:
            try:
                _reranker = SentenceTransformerRerank(model=app_settings.reranker_model, top_n=top_n)
                print(f"✅ Reranker loaded: {app_settings.reranker_model}")
            except Exception as exc:
                print(f"⚠️  Reranker not available ({exc}). Using cosine ranking.")
                return None
        else:
            _reranker.top_n = top_n
        return _reranker


# ── Chat Engine Registry — max 50 sessions, TTL 30 min ────────
_CHAT_ENGINES: TTLCache = TTLCache(maxsize=50, ttl=1800)


def _effective_query_mode(index: VectorStoreIndex) -> VectorStoreQueryMode:
    """Determines the actual mode based on the underlying QdrantVectorStore of the index.

    Even if ENABLE_HYBRID=true in settings, the store may be dense-only if
    the collection was created without sparse vectors (e.g. old or empty collection).
    Checking the _enable_hybrid attribute of the store avoids the LlamaIndex ValueError.
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
    """Gets or creates a chat engine with memory, reranking and optional HyDE."""
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
                print("🔮 HyDE enabled for chat engine")
            except Exception as exc:
                print(f"⚠️  HyDE not available for chat ({exc}). Using standard retriever.")
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
    """Removes all chat engines linked to the session."""
    removed = [k for k in list(_CHAT_ENGINES) if k.startswith(f"{session_id}:")]
    for k in removed:
        del _CHAT_ENGINES[k]
    return bool(removed)


def _nodes_to_sources(nodes) -> list[SourceInfo]:
    return [
        SourceInfo(
            filename=node.metadata.get("file_name") or node.metadata.get("source", "unknown"),
            text=(node.text or "")[:600],
            score=round(float(node.score or 0.0), 4),
        )
        for node in (nodes or [])
    ]


def _build_filters(file_type: Optional[str]) -> Optional[MetadataFilters]:
    """Builds optional MetadataFilters from query parameters."""
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
    Single-turn RAG query with hybrid search and optional reranking.

    - file_type_filter: filter by extension ('.pdf', '.txt', etc.)
    - use_hyde: apply HyDE (Hypothetical Document Embeddings) before searching
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

    # HyDE: generate hypothetical document before searching
    apply_hyde = use_hyde or app_settings.enable_hyde
    engine = base_engine
    if apply_hyde:
        try:
            hyde_transform = HyDEQueryTransform(include_original=True)
            engine = TransformQueryEngine(base_engine, query_transform=hyde_transform)
        except Exception as exc:
            print(f"⚠️  HyDE not available ({exc}). Using query without transformation.")

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
    Generates SSE events for multi-turn chat with reranking and optional HyDE.
    Sends tokens with event='token' and at the end sources with event='sources'.
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
    """Multi-turn chat without streaming (fallback)."""
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
