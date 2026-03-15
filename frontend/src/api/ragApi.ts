import axios from 'axios'
import type {
  HealthResponse,
  UploadResponse,
  IngestRequest,
  IngestResponse,
  IngestStatus,
  QueryRequest,
  QueryResponse,
  ChatRequest,
  ChatResponse,
  FeedbackRequest,
  DocumentsResponse,
  MessageResponse,
  CollectionsResponse,
  CollectionCreateRequest,
  RagStreamError,
  RagConfig,
  EvalRequest,
  EvalStatus,
} from '@/types/rag'

/** Builds a generic RagStreamError when there is no structured payload */
function _networkError(detail: string): RagStreamError {
  return { detail, error_code: 'connection_error', suggestion: 'Check your connection and make sure the server is running.' }
}

function _serverError(status: number): RagStreamError {
  if (status === 503) return { detail: 'Service unavailable.', error_code: 'qdrant_unavailable', suggestion: 'Ingest documents first using the \'Ingest\' button.' }
  if (status === 429) return { detail: 'Too many requests.', error_code: 'llm_quota', suggestion: 'Wait a few seconds before retrying.' }
  if (status === 401) return { detail: 'Unauthorized.', error_code: 'llm_auth', suggestion: 'Check your API Key.' }
  return { detail: `Server error (HTTP ${status}).`, error_code: 'unknown', suggestion: 'Check the server logs for more details.' }
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const ragApi = {
  /** GET /health */
  checkHealth(): Promise<HealthResponse> {
    return api.get<HealthResponse>('/health').then(r => r.data)
  },

  /** POST /upload?collection=... — multipart/form-data */
  uploadDocument(file: File, collection?: string): Promise<UploadResponse> {
    const form = new FormData()
    form.append('file', file)
    const params = collection ? { collection } : {}
    return api
      .post<UploadResponse>('/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        params,
      })
      .then(r => r.data)
  },

  /** GET /documents?collection=... */
  listDocuments(collection?: string): Promise<DocumentsResponse> {
    return api.get<DocumentsResponse>('/documents', { params: collection ? { collection } : {} }).then(r => r.data)
  },

  /** DELETE /documents/:filename?collection=... */
  deleteDocument(filename: string, collection?: string): Promise<MessageResponse> {
    return api
      .delete<MessageResponse>(`/documents/${encodeURIComponent(filename)}`, {
        params: collection ? { collection } : {},
      })
      .then(r => r.data)
  },

  /** POST /ingest?collection=... */
  triggerIngest(payload: IngestRequest = {}, collection?: string): Promise<IngestResponse> {
    return api.post<IngestResponse>('/ingest', payload, { params: collection ? { collection } : {} }).then(r => r.data)
  },

  /** POST /query?collection=... */
  queryRag(payload: QueryRequest, collection?: string): Promise<QueryResponse> {
    return api.post<QueryResponse>('/query', payload, { params: collection ? { collection } : {} }).then(r => r.data)
  },

  /** GET /ingest/status?collection=... */
  getIngestStatus(collection?: string): Promise<IngestStatus> {
    return api.get<IngestStatus>('/ingest/status', { params: collection ? { collection } : {} }).then(r => r.data)
  },

  /** DELETE /collection (reset default — compatibility) */
  resetCollection(): Promise<MessageResponse> {
    return api.delete<MessageResponse>('/collection').then(r => r.data)
  },

  // ── Collection management ──────────────────────────────────

  /** GET /collections */
  listCollections(): Promise<CollectionsResponse> {
    return api.get<CollectionsResponse>('/collections').then(r => r.data)
  },

  /** POST /collections */
  createCollection(payload: CollectionCreateRequest): Promise<MessageResponse> {
    return api.post<MessageResponse>('/collections', payload).then(r => r.data)
  },

  /** DELETE /collections/:name */
  deleteCollection(name: string): Promise<MessageResponse> {
    return api.delete<MessageResponse>(`/collections/${encodeURIComponent(name)}`).then(r => r.data)
  },

  // ── Chat ───────────────────────────────────────────────────

  /** POST /chat — multi-turn chat without streaming */
  chat(payload: ChatRequest, collection?: string): Promise<ChatResponse> {
    return api.post<ChatResponse>('/chat', payload, { params: collection ? { collection } : {} }).then(r => r.data)
  },

  /** DELETE /chat/:sessionId */
  clearChatSession(sessionId: string): Promise<MessageResponse> {
    return api.delete<MessageResponse>(`/chat/${encodeURIComponent(sessionId)}`).then(r => r.data)
  },

  /** POST /feedback */
  submitFeedback(payload: FeedbackRequest): Promise<MessageResponse> {
    return api.post<MessageResponse>('/feedback', payload).then(r => r.data)
  },

  // ── Evaluation ─────────────────────────────────────────────

  /** POST /eval — starts evaluation in the background */
  startEval(payload: EvalRequest): Promise<{ eval_id: string; message: string }> {
    return api.post('/eval', payload).then(r => r.data)
  },

  /** GET /eval/:evalId — status and results */
  getEvalStatus(evalId: string): Promise<EvalStatus> {
    return api.get<EvalStatus>(`/eval/${encodeURIComponent(evalId)}`).then(r => r.data)
  },

  /** GET /config */
  getConfig(): Promise<RagConfig> {
    return api.get<RagConfig>('/config').then(r => r.data)
  },

  /** PUT /config */
  updateConfig(body: Partial<RagConfig>): Promise<{ ok: boolean }> {
    return api.put<{ ok: boolean }>('/config', body).then(r => r.data)
  },

  /**
   * POST /chat/stream?collection=... — multi-turn chat with SSE streaming.
   * Calls onToken for each token received, onSources at the end with source
   * data, and onDone on completion. onError with RagStreamError on failure.
   */
  async chatStream(
    payload: ChatRequest,
    onToken: (token: string) => void,
    onSources: (data: { sources: ChatResponse['sources']; nodes_retrieved: number; query_id: string; session_id: string }) => void,
    onDone: () => void,
    onError: (err: RagStreamError) => void,
    collection?: string,
  ): Promise<void> {
    const url = collection
      ? `${BASE_URL}/chat/stream?collection=${encodeURIComponent(collection)}`
      : `${BASE_URL}/chat/stream`
    let response: Response
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify(payload),
      })
    } catch {
      onError(_networkError('Network error while connecting to the server.'))
      return
    }

    if (!response.ok || !response.body) {
      // Try to read JSON with error_code from the body (e.g. 503 with structured detail)
      try {
        const errBody = await response.json()
        if (errBody.error_code) {
          onError(errBody as RagStreamError)
        } else {
          onError({ ..._serverError(response.status), detail: errBody.detail ?? _serverError(response.status).detail })
        }
      } catch {
        onError(_serverError(response.status))
      }
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        // Normalize \r\n → \n for compatibility with sse-starlette 3.x
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')

        // Process SSE blocks separated by \n\n
        let boundary: number
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const block = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)

          let event = 'message'
          const dataLines: string[] = []
          for (const line of block.split('\n')) {
            if (line.startsWith('event: ')) event = line.slice(7).trim()
            else if (line.startsWith('data: ')) dataLines.push(line.slice(6))
          }
          const data = dataLines.join('\n')

          if (event === 'token') {
            onToken(data)
          } else if (event === 'sources') {
            try { onSources(JSON.parse(data)) } catch { /* ignorar */ }
          } else if (event === 'done' || data === '[DONE]') {
            onDone()
            return
          } else if (event === 'error') {
            try {
              const parsed = JSON.parse(data)
              onError(parsed.error_code
                ? (parsed as RagStreamError)
                : { detail: parsed.detail ?? data, error_code: 'unknown', suggestion: '' })
            } catch {
              onError({ detail: data, error_code: 'unknown', suggestion: 'Check the server logs.' })
            }
            return
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
    onDone()
  },
}

export default ragApi
