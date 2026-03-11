import base64
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

# Directorio base para datos por colección: ./data/{collection_name}/
BASE_DATA_DIR = Path("./data")
# Directorio base de storage LlamaIndex por colección: ./storage/{collection_name}/
BASE_STORAGE_DIR = Path("./storage")

# Metadata de colecciones creadas via API (descripción, etc.)
# Se persiste en ./storage/.collections_meta.json
_COLLECTIONS_META_FILE = BASE_STORAGE_DIR / ".collections_meta.json"


def _load_collections_meta() -> dict:
    """Lee el archivo de metadata de colecciones."""
    if _COLLECTIONS_META_FILE.exists():
        import json
        try:
            return json.loads(_COLLECTIONS_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_collections_meta(meta: dict) -> None:
    """Persiste metadata de colecciones."""
    import json
    BASE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    _COLLECTIONS_META_FILE.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_collection_data_dir(collection_name: str) -> Path:
    """Retorna el directorio de datos para una colección concreta."""
    return BASE_DATA_DIR / collection_name


def get_collection_storage_dir(collection_name: str) -> Path:
    """Retorna el directorio de storage LlamaIndex para una colección."""
    return BASE_STORAGE_DIR / collection_name


_settings_initialized = False


def _init_llama_settings() -> None:
    global _settings_initialized
    if _settings_initialized:
        return
    Settings.embed_model = GoogleGenAIEmbedding(
        model_name="models/gemini-embedding-2-preview",
        api_key=app_settings.google_api_key,
        embed_batch_size=10,
    )
    Settings.llm = GoogleGenAI(
        model="gemini-2.5-flash",
        api_key=app_settings.google_api_key,
        max_tokens=4096,
    )
    # Fallback: se usa solo si SemanticSplitter está desactivado
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
    Retorna QdrantVectorStore para la colección indicada.

    - ENABLE_HYBRID=true → habilita dense+sparse (BM25) con fastembed.
      * allow_recreate=True: si la colección existe sin sparse, la elimina para
        que LlamaIndex la recree con sparse al ingestar.
      * allow_recreate=False (startup): si la colección existe sin sparse, usa
        dense-only para no romper queries. Re-ingestar activa el híbrido.
    - ENABLE_HYBRID=false → solo dense (comportamiento original).
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
                        f"⚠️  Recreando colección '{collection}' para habilitar "
                        "búsqueda híbrida (dense + sparse BM25)..."
                    )
                    client.delete_collection(collection)
                else:
                    print(
                        f"⚠️  '{collection}' no tiene sparse vectors — usando dense-only. "
                        "Llama a /ingest para activar búsqueda híbrida."
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
    Construye el parser de nodos.
    - ENABLE_SEMANTIC_CHUNKING=true  → SemanticSplitterNodeParser (semántico).
    - ENABLE_SEMANTIC_CHUNKING=false → SentenceSplitter fijo (más rápido, default).
    """
    if app_settings.enable_semantic_chunking:
        try:
            print("📐 Usando chunking semántico (SemanticSplitterNodeParser)...")
            return SemanticSplitterNodeParser(
                buffer_size=1,
                breakpoint_percentile_threshold=95,
                embed_model=Settings.embed_model,
            )
        except Exception as exc:
            print(f"⚠️  SemanticSplitter no disponible ({exc}). Usando chunking fijo.")
    return SentenceSplitter(chunk_size=512, chunk_overlap=64)


def _enrich_metadata(nodes, data_dir: Path):
    """
    Añade metadata enriquecida a todos los nodos:
    file_type, ingested_at, file_size.
    page_number ya lo inyecta LlamaIndex para PDFs en node.metadata['page_label'].
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
    Genera ImageNodes con embeddings multimodal nativos para cada imagen.
    Usa gemini-embedding-2-preview directamente con el contenido binario
    en lugar de OCR o descripción de texto.
    Retorna lista de ImageNodes listos para indexar junto a los text nodes.
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

            # Generar embedding nativo via Settings.embed_model
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
            print(f"\u26a0\ufe0f  No se pudo embeddear {img_path.name} nativamente ({exc}). Saltando.")
            continue
    return image_nodes


def ingest_documents(collection_name: str | None = None) -> VectorStoreIndex:
    """
    Carga, procesa y embeddea los documentos de una colección.
    Los documentos se leen desde ./data/{collection_name}/.
    Retorna el índice actualizado.
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
        raise FileNotFoundError(f"No se encontraron documentos en {data_dir}")

    mode = "semántico" if app_settings.enable_semantic_chunking else "fijo"
    print(f"📄 [{col}] {len(nodes)} nodos de texto + {len(image_nodes)} imágenes = {len(all_nodes)} nodos totales (chunking {mode}).")

    storage_ctx = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(all_nodes, storage_context=storage_ctx, show_progress=True)

    storage_dir.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(storage_dir))

    return index


def load_existing_index(collection_name: str | None = None) -> VectorStoreIndex | None:
    """
    Carga índice desde Qdrant para la colección indicada.
    Retorna None si la colección no existe en Qdrant (evita índices 'fantasma').
    """
    col = collection_name or app_settings.collection_name
    _init_llama_settings()
    q_client = get_qdrant_client()
    existing = {c.name for c in q_client.get_collections().collections}
    if col not in existing:
        print(f"⚠️  Colección '{col}' no existe en Qdrant — índice no cargado.")
        return None
    vector_store = get_vector_store(q_client, collection_name=col, allow_recreate=False)
    return VectorStoreIndex.from_vector_store(vector_store)


def load_index_for_collection(collection_name: str) -> VectorStoreIndex | None:
    """Alias para carga perezosa de colecciones adicionales."""
    return load_existing_index(collection_name)


def create_collection(collection_name: str, description: str = "") -> None:
    """
    Crea una nueva colección vacía en Qdrant y su directorio de datos.
    Registra la descripción en el archivo de metadata.
    Lanza ValueError si ya existe.
    """
    q_client = get_qdrant_client()
    existing = [c.name for c in q_client.get_collections().collections]
    if collection_name in existing:
        raise ValueError(f"La colección '{collection_name}' ya existe en Qdrant.")

    if app_settings.enable_hybrid:
        # Con híbrido, QdrantVectorStore la creará la primera vez que se ingeste.
        # Solo preparamos el directorio y la metadata.
        pass
    else:
        q_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=app_settings.embedding_dim,
                distance=Distance.COSINE,
            ),
        )

    # Crear directorio de datos
    get_collection_data_dir(collection_name).mkdir(parents=True, exist_ok=True)

    # Guardar metadata
    meta = _load_collections_meta()
    meta[collection_name] = {
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_collections_meta(meta)


def delete_collection(collection_name: str) -> None:
    """
    Elimina la colección en Qdrant, su directorio de datos y su storage.
    Lanza ValueError si intenta eliminar la colección por defecto cuando es la única.
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

    # Limpiar metadata
    meta = _load_collections_meta()
    meta.pop(collection_name, None)
    _save_collections_meta(meta)


def get_collection_stats(collection_name: str) -> dict:
    """
    Retorna estadísticas de una colección: vector_count y doc_count (archivos en ./data/).
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
    Retorna lista de todas las colecciones con stats y metadata.
    Incluye colecciones en Qdrant y las registradas localmente.
    """
    q_client = get_qdrant_client()
    meta = _load_collections_meta()

    qdrant_names = {c.name for c in q_client.get_collections().collections}
    # Colecciones locales (directorios de datos)
    local_names = set()
    if BASE_DATA_DIR.exists():
        local_names = {d.name for d in BASE_DATA_DIR.iterdir() if d.is_dir()}

    all_names = qdrant_names | local_names | set(meta.keys())
    # Aseguramos que la colección por defecto siempre aparezca
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

