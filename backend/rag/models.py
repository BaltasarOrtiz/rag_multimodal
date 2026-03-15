from pydantic import BaseModel, Field
from typing import Optional, Literal
import uuid


# ── Collections ───────────────────────────────────────────────

class CollectionCreateRequest(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=64,
        pattern=r'^[a-z0-9][a-z0-9_\-]*$',
        description="Collection name (lowercase letters, numbers, _ and - only).",
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
    tema: str = Field(description="Main topic of the document")
    descripcion: str = Field(description="Detailed summary of the content")
    elementos_visuales: str = Field(description="Diagrams, tables or formulas identified")
    explicacion: str = Field(description="Step-by-step explanation of the concept")


class IngestRequest(BaseModel):
    force_reingest: bool = False


class QueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=10)
    file_type_filter: Optional[str] = Field(
        default=None,
        description="Filter by file extension: '.pdf', '.txt', '.md', etc.",
    )
    use_hyde: bool = Field(
        default=False,
        description="Apply HyDE (Hypothetical Document Embeddings) before searching.",
    )


class SourceInfo(BaseModel):
    filename: str
    text: str       # chunk content (truncated)
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
        description="Filter by file extension: '.pdf', '.txt', '.md', etc.",
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


# ── RAGAS Evaluation ──────────────────────────────────────────

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
    progress: int          # 0-100
    metrics: Optional[EvalMetrics] = None
    results: Optional[list[EvalQuestionResult]] = None
    error: Optional[str] = None
