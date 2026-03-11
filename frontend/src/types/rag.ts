// ──────────────────────────────────────────────────────────
// RAG API TypeScript Types
// Mirrors the Pydantic schemas in backend/rag/models.py
// ──────────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok' | 'error'
  index_loaded: boolean
}

export interface UploadResponse {
  message: string
}

export interface IngestRequest {
  force_reingest?: boolean
}

export interface IngestResponse {
  message: string
}

export interface QueryRequest {
  query: string
  top_k?: number
}

export interface SourceInfo {
  filename: string
  text: string
  score: number
}

export interface QueryResponse {
  query_id: string
  answer: string
  sources: SourceInfo[]
  nodes_retrieved: number
}

export interface ChatRequest {
  message: string
  session_id: string
  top_k?: number
}

export interface ChatResponse {
  query_id: string
  answer: string
  sources: SourceInfo[]
  nodes_retrieved: number
  session_id: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceInfo[]
  nodes_retrieved?: number
  query_id?: string
  timestamp: number
  rating?: 1 | -1
}

export interface FeedbackRequest {
  query_id: string
  query: string
  answer: string
  rating: 1 | -1
  comment?: string
}

export interface DocumentInfo {
  name: string
  size: number
  ext: string
}

export interface DocumentsResponse {
  documents: DocumentInfo[]
  total: number
  collection: string
}

export interface MessageResponse {
  message: string
}

export interface IngestStatus {
  status: 'idle' | 'running' | 'done' | 'failed'
  message: string
  started_at: string | null
  finished_at: string | null
  collection?: string
  total_docs?: number
  processed_docs?: number
}

// ── Colecciones ──────────────────────────────────────────────

export interface CollectionInfo {
  name: string
  description: string
  vector_count: number
  doc_count: number
  is_default: boolean
}

export interface CollectionsResponse {
  collections: CollectionInfo[]
  active: string
}

export interface CollectionCreateRequest {
  name: string
  description?: string
}

// ── Errores estructurados ──────────────────────────────────────

export type RagErrorCode =
  | 'qdrant_not_found'
  | 'qdrant_unavailable'
  | 'qdrant_error'
  | 'llm_quota'
  | 'llm_auth'
  | 'llm_unavailable'
  | 'llm_timeout'
  | 'llm_error'
  | 'hybrid_config'
  | 'connection_error'
  | 'timeout'
  | 'unknown'

export interface RagStreamError {
  detail: string
  error_code: RagErrorCode
  suggestion: string
}
