import base64
import threading
from datetime import datetime, timezone
from pathlib import Path
from llama_index.core import (
    Settings, StorageContext, VectorStoreIndex,
    SimpleDirectoryReader,
)
from llama_index.core.schema import ImageNode
from llama_index.core.node_parser import SemanticSplitterNodeParser, SentenceSplitter
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
import qdrant_client
from qdrant_client.models import Distance, VectorParams

from config import settings as app_settings
from logger import logger

# Base data directory per collection: ./data/{collection_name}/
BASE_DATA_DIR = Path("./data")
# Base LlamaIndex storage directory per collection: ./storage/{collection_name}/
BASE_STORAGE_DIR = Path("./storage")

# Metadata for collections created via API (description, etc.)
# Persisted in ./storage/.collections_meta.json
_COLLECTIONS_META_FILE = BASE_STORAGE_DIR / ".collections_meta.json"


def _load_collections_meta() -> dict:
    """Reads the collections metadata file."""
    if _COLLECTIONS_META_FILE.exists():
        import json
        try:
            return json.loads(_COLLECTIONS_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_collections_meta(meta: dict) -> None:
    """Persists collections metadata."""
    import json
    BASE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    _COLLECTIONS_META_FILE.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_collection_data_dir(collection_name: str) -> Path:
    """Returns the data directory for a specific collection."""
    return BASE_DATA_DIR / collection_name


def get_collection_storage_dir(collection_name: str) -> Path:
    """Returns the LlamaIndex storage directory for a collection."""
    return BASE_STORAGE_DIR / collection_name


_settings_initialized = False
_init_lock = threading.Lock()


def _init_llama_settings() -> None:
    global _settings_initialized
    with _init_lock:
        if _settings_initialized:
            return
        Settings.embed_model = GoogleGenAIEmbedding(
            model_name=app_settings.embedding_model,
            api_key=app_settings.google_api_key,
            embed_batch_size=10,
        )
        Settings.llm = GoogleGenAI(
            model=app_settings.llm_model,
            api_key=app_settings.google_api_key,
            max_tokens=4096,
        )
        # Fallback: used only if SemanticSplitter is disabled
        Settings.chunk_size = 512
        Settings.chunk_overlap = 64
        _settings_initialized = True


def get_qdrant_client():
    return qdrant_client.QdrantClient(
        host=app_settings.qdrant_host,
        port=app_settings.qdrant_port,
    )


def get_vector_store(
    client,
    collection_name: str | None = None,
    allow_recreate: bool = False,
) -> QdrantVectorStore:
    """
    Returns QdrantVectorStore for the indicated collection.

    - ENABLE_HYBRID=true → enables dense+sparse (BM25) with fastembed.
      * allow_recreate=True: if the collection exists without sparse vectors, deletes it so
        LlamaIndex recreates it with sparse on ingestion.
      * allow_recreate=False (startup): if the collection exists without sparse vectors, uses
        dense-only to avoid breaking queries. Re-ingesting activates hybrid mode.
    - ENABLE_HYBRID=false → dense only (original behavior).
    """
    collection = collection_name or app_settings.collection_name
    if app_settings.enable_hybrid:
        existing = [c.name for c in client.get_collections().collections]
        if collection in existing:
            col_info = client.get_collection(collection)
            sparse_cfg = getattr(col_info.config.params, "sparse_vectors_config", None)
            if not sparse_cfg:
                if allow_recreate:
                    print(
                        f"⚠️  Recreating collection '{collection}' to enable "
                        "hybrid search (dense + sparse BM25)..."
                    )
                    client.delete_collection(collection)
                else:
                    print(
                        f"⚠️  '{collection}' has no sparse vectors — using dense-only. "
                        "Call /ingest to activate hybrid search."
                    )
                    return QdrantVectorStore(client=client, collection_name=collection)
        return QdrantVectorStore(
            client=client,
            collection_name=collection,
            enable_hybrid=True,
            batch_size=20,
        )
    else:
        existing = [c.name for c in client.get_collections().collections]
        if collection not in existing:
            client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(
                    size=app_settings.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
        return QdrantVectorStore(client=client, collection_name=collection)


def _build_node_parser():
    """
    Builds the node parser.
    - ENABLE_SEMANTIC_CHUNKING=true  → SemanticSplitterNodeParser (semantic).
    - ENABLE_SEMANTIC_CHUNKING=false → Fixed SentenceSplitter (faster, default).
    """
    if app_settings.enable_semantic_chunking:
        try:
            print("📐 Using semantic chunking (SemanticSplitterNodeParser)...")
            return SemanticSplitterNodeParser(
                buffer_size=1,
                breakpoint_percentile_threshold=95,
                embed_model=Settings.embed_model,
            )
        except Exception as exc:
            print(f"⚠️  SemanticSplitter not available ({exc}). Using fixed chunking.")
    return SentenceSplitter(chunk_size=512, chunk_overlap=64)


def _enrich_metadata(nodes, data_dir: Path):
    """
    Adds enriched metadata to all nodes:
    file_type, ingested_at, file_size.
    page_number is already injected by LlamaIndex for PDFs in node.metadata['page_label'].
    """
    ingested_at = datetime.now(timezone.utc).isoformat()
    for node in nodes:
        source = node.metadata.get("file_name") or node.metadata.get("source", "")
        file_path = data_dir / source if source else None
        node.metadata.setdefault("file_type", Path(source).suffix.lower() if source else "")
        node.metadata["ingested_at"] = ingested_at
        node.metadata["file_size"] = (
            file_path.stat().st_size if file_path and file_path.exists() else 0
        )
    return nodes


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _embed_images_natively(data_dir: Path) -> list:
    """
    Generates ImageNodes with native multimodal embeddings for each image.
    Uses gemini-embedding-2-preview directly with binary content
    instead of OCR or text description.
    Returns a list of ImageNodes ready to index alongside text nodes.
    """
    image_nodes = []
    for img_path in data_dir.iterdir():
        if not img_path.is_file():
            continue
        if img_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            raw = img_path.read_bytes()
            ext = img_path.suffix.lower().lstrip(".")
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            b64 = base64.b64encode(raw).decode("utf-8")
            data_uri = f"data:image/{mime};base64,{b64}"

            # Generate native embedding via Settings.embed_model
            embedding = Settings.embed_model.get_text_embedding(data_uri)

            node = ImageNode(
                image_path=str(img_path),
                image_url=str(img_path),
                embedding=embedding,
                metadata={
                    "file_name": img_path.name,
                    "file_type": img_path.suffix.lower(),
                    "source": img_path.name,
                    "multimodal_native": True,
                },
            )
            image_nodes.append(node)
            print(f"\U0001f5bc\ufe0f  Imagen embedeada nativamente: {img_path.name}")
        except Exception as exc:
            logger.warning(
                "Could not embed image natively",
                filename=img_path.name,
                error=str(exc),
            )
            continue
    return image_nodes


def ingest_documents(collection_name: str | None = None) -> VectorStoreIndex:
    """
    Loads, processes and embeds the documents of a collection.
    Documents are read from ./data/{collection_name}/.
    Returns the updated index.
    """
    col = collection_name or app_settings.collection_name
    data_dir = get_collection_data_dir(col)
    storage_dir = get_collection_storage_dir(col)

    _init_llama_settings()
    q_client = get_qdrant_client()
    vector_store = get_vector_store(q_client, collection_name=col, allow_recreate=True)

    docs = SimpleDirectoryReader(
        str(data_dir),
        required_exts=[".pdf", ".txt", ".md"],
    ).load_data()

    parser = _build_node_parser()
    nodes = parser.get_nodes_from_documents(docs, show_progress=True)
    nodes = _enrich_metadata(nodes, data_dir)

    image_nodes = _embed_images_natively(data_dir)
    all_nodes = nodes + image_nodes

    if not all_nodes:
        raise FileNotFoundError(f"No documents found in {data_dir}")

    mode = "semantic" if app_settings.enable_semantic_chunking else "fixed"
    print(f"📄 [{col}] {len(nodes)} text nodes + {len(image_nodes)} images = {len(all_nodes)} total nodes (chunking {mode}).")

    storage_ctx = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(all_nodes, storage_context=storage_ctx, show_progress=True)

    storage_dir.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(storage_dir))

    return index


def load_existing_index(collection_name: str | None = None) -> VectorStoreIndex | None:
    """
    Loads index from Qdrant for the indicated collection.
    Returns None if the collection does not exist in Qdrant (avoids 'ghost' indexes).
    """
    col = collection_name or app_settings.collection_name
    _init_llama_settings()
    q_client = get_qdrant_client()
    existing = {c.name for c in q_client.get_collections().collections}
    if col not in existing:
        print(f"⚠️  Collection '{col}' does not exist in Qdrant — index not loaded.")
        return None
    vector_store = get_vector_store(q_client, collection_name=col, allow_recreate=False)
    return VectorStoreIndex.from_vector_store(vector_store)


def load_index_for_collection(collection_name: str) -> VectorStoreIndex | None:
    """Alias for lazy loading of additional collections."""
    return load_existing_index(collection_name)


def create_collection(collection_name: str, description: str = "") -> None:
    """
    Creates a new empty collection in Qdrant and its data directory.
    Registers the description in the metadata file.
    Raises ValueError if it already exists.
    """
    q_client = get_qdrant_client()
    existing = [c.name for c in q_client.get_collections().collections]
    if collection_name in existing:
        raise ValueError(f"Collection '{collection_name}' already exists in Qdrant.")

    if app_settings.enable_hybrid:
        # With hybrid, QdrantVectorStore will create it the first time documents are ingested.
        # We only prepare the directory and metadata.
        pass
    else:
        q_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=app_settings.embedding_dim,
                distance=Distance.COSINE,
            ),
        )

    # Create data directory
    get_collection_data_dir(collection_name).mkdir(parents=True, exist_ok=True)

    # Save metadata
    meta = _load_collections_meta()
    meta[collection_name] = {
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_collections_meta(meta)


def delete_collection(collection_name: str) -> None:
    """
    Deletes the collection from Qdrant, its data directory and its storage.
    Raises ValueError if attempting to delete the default collection when it is the only one.
    """
    import shutil
    q_client = get_qdrant_client()
    existing = [c.name for c in q_client.get_collections().collections]
    if collection_name in existing:
        q_client.delete_collection(collection_name)

    data_dir = get_collection_data_dir(collection_name)
    if data_dir.exists():
        shutil.rmtree(data_dir)

    storage_dir = get_collection_storage_dir(collection_name)
    if storage_dir.exists():
        shutil.rmtree(storage_dir)

    # Clean up metadata
    meta = _load_collections_meta()
    meta.pop(collection_name, None)
    _save_collections_meta(meta)


def get_collection_stats(collection_name: str) -> dict:
    """
    Returns statistics for a collection: vector_count and doc_count (files in ./data/).
    """
    q_client = get_qdrant_client()
    vector_count = 0
    try:
        info = q_client.get_collection(collection_name)
        vector_count = info.vectors_count or 0
    except Exception:
        pass

    data_dir = get_collection_data_dir(collection_name)
    doc_count = 0
    if data_dir.exists():
        doc_count = sum(
            1 for f in data_dir.iterdir()
            if f.is_file() and f.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}
        )

    return {"vector_count": vector_count, "doc_count": doc_count}


def list_all_collections() -> list[dict]:
    """
    Returns a list of all collections with stats and metadata.
    Includes collections in Qdrant and those registered locally.
    """
    q_client = get_qdrant_client()
    meta = _load_collections_meta()

    qdrant_names = {c.name for c in q_client.get_collections().collections}
    # Local collections (data directories)
    local_names = set()
    if BASE_DATA_DIR.exists():
        local_names = {d.name for d in BASE_DATA_DIR.iterdir() if d.is_dir()}

    all_names = qdrant_names | local_names | set(meta.keys())
    # Ensure the default collection always appears
    all_names.add(app_settings.collection_name)

    result = []
    for name in sorted(all_names):
        stats = get_collection_stats(name)
        col_meta = meta.get(name, {})
        result.append({
            "name": name,
            "description": col_meta.get("description", ""),
            "vector_count": stats["vector_count"],
            "doc_count": stats["doc_count"],
            "is_default": name == app_settings.collection_name,
        })
    return result

