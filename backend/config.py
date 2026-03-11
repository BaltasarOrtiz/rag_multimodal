from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Requerida — falla al arrancar si no está definida
    google_api_key: str

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    # RAG
    collection_name: str = "facultad_rag"
    embedding_dim: int = 3072
    enable_hybrid: bool = True
    enable_reranker: bool = True
    enable_hyde: bool = False
    enable_semantic_chunking: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-2-v2"
    hybrid_alpha: float = 0.5

    # API
    max_upload_mb: int = 50
    api_port: int = 8000
    # Opcional — auth desactivada si None
    api_key: str | None = None
    # CORS — orígenes permitidos separados por coma
    cors_origins: str = "http://localhost,http://localhost:80,http://localhost:5173,http://localhost:3000,http://frontend"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )



settings = Settings()

