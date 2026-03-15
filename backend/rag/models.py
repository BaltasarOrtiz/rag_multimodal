from pydantic import BaseModel, Field
from typing import Optional, Literal
import uuid


# ── Colecciones ───────────────────────────────────────────────

class CollectionCreateRequest(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=64,
        pattern=r'^[a-z0-9][a-z0-9_\-]*$',
        description="Nombre de la colección (solo minúsculas, números, _ y -).",
    )
    description: str = Field(default="", max_length=256)


class CollectionInfo(BaseModel):
    name: str
    description: str = ""
    vector_count: int = 0
    doc_count: int = 0
    is_default: bool = False


class CollectionsResponse(BaseModel):
    collections: list[CollectionInfo]
    active: str


class FacultadDocSchema(BaseModel):
    tema: str = Field(description="Tema principal del documento")
    descripcion: str = Field(description="Resumen detallado del contenido")
    elementos_visuales: str = Field(description="Diagramas, tablas o fórmulas identificadas")
    explicacion: str = Field(description="Explicación paso a paso del concepto")


class IngestRequest(BaseModel):
    force_reingest: bool = False


class QueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=10)
    file_type_filter: Optional[str] = Field(
        default=None,
        description="Filtrar por extensión de archivo: '.pdf', '.txt', '.md', etc.",
    )
    use_hyde: bool = Field(
        default=False,
        description="Aplicar HyDE (Hypothetical Document Embeddings) antes de buscar.",
    )


class SourceInfo(BaseModel):
    filename: str
    text: str       # contenido del chunk (truncado)
    score: float    # relevance score


class QueryResponse(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    answer: str
    sources: list[SourceInfo] = []
    nodes_retrieved: int = 0


class ChatRequest(BaseModel):
    message: str
    session_id: str
    top_k: int = Field(default=3, ge=1, le=10)
    file_type_filter: Optional[str] = Field(
        default=None,
        description="Filtrar por extensión de archivo: '.pdf', '.txt', '.md', etc.",
    )


class ChatResponse(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    answer: str
    sources: list[SourceInfo] = []
    nodes_retrieved: int = 0
    session_id: str


class FeedbackRequest(BaseModel):
    query_id: str
    query: str
    answer: str
    rating: Literal[1, -1]
    comment: Optional[str] = None


class IngestStatus(BaseModel):
    status: Literal["idle", "running", "done", "failed"]
    message: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    collection: Optional[str] = None
    total_docs: Optional[int] = 0
    processed_docs: Optional[int] = 0


# ── Evaluación RAGAS ──────────────────────────────────────────

class EvalQuestion(BaseModel):
    question: str = Field(min_length=1)
    ground_truth: str = Field(min_length=1)


class EvalRequest(BaseModel):
    questions: list[EvalQuestion] = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    collection: Optional[str] = None


class EvalQuestionResult(BaseModel):
    question: str
    answer: str
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_recall: float
    context_precision: float
    nodes_retrieved: int


class EvalMetrics(BaseModel):
    faithfulness: float
    answer_relevancy: float
    context_recall: float
    context_precision: float


class EvalStatus(BaseModel):
    eval_id: str
    status: Literal["running", "done", "failed"]
    timestamp: str
    n_questions: int
    top_k: int
    questions_done: int
    progress: int          # 0–100
    metrics: Optional[EvalMetrics] = None
    results: Optional[list[EvalQuestionResult]] = None
    error: Optional[str] = None
