import { ref, watchEffect } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import ragApi from '@/api/ragApi'
import { useCollectionStore } from '@/stores/useCollectionStore'
import type { QueryResponse, DocumentInfo, IngestStatus, ChatMessage, SourceInfo, RagStreamError } from '@/types/rag'

// ── Health ──────────────────────────────────────────────────
export function useHealth() {
  const status = ref<'ok' | 'error' | 'loading'>('loading')
  const indexLoaded = ref(false)

  async function refresh() {
    try {
      const res = await ragApi.checkHealth()
      status.value = res.status
      indexLoaded.value = res.index_loaded
    } catch {
      status.value = 'error'
      indexLoaded.value = false
    }
  }

  // Poll every 10 seconds
  useIntervalFn(refresh, 10_000, { immediateCallback: true })

  return { status, indexLoaded, refresh }
}

// ── Documents ────────────────────────────────────────────────
export function useDocuments() {
  const collectionStore = useCollectionStore()
  const documents = ref<DocumentInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchDocuments() {
    loading.value = true
    error.value = null
    try {
      const col = collectionStore.activeCollection || undefined
      const res = await ragApi.listDocuments(col)
      documents.value = res.documents
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Error al obtener documentos'
    } finally {
      loading.value = false
    }
  }

  async function upload(file: File) {
    loading.value = true
    error.value = null
    try {
      const col = collectionStore.activeCollection || undefined
      const res = await ragApi.uploadDocument(file, col)
      await fetchDocuments()
      return res.message
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Error al subir archivo'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteDocument(name: string) {
    loading.value = true
    error.value = null
    try {
      const col = collectionStore.activeCollection || undefined
      const res = await ragApi.deleteDocument(name, col)
      await fetchDocuments()
      return res.message
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Error al eliminar documento'
      throw e
    } finally {
      loading.value = false
    }
  }

  return { documents, loading, error, fetchDocuments, upload, deleteDocument }
}

// ── Ingest ───────────────────────────────────────────────────
export function useIngest() {
  const collectionStore = useCollectionStore()
  const loading = ref(false)
  const message = ref<string | null>(null)
  const error = ref<string | null>(null)

  async function ingest(force = false) {
    loading.value = true
    message.value = null
    error.value = null
    try {
      const col = collectionStore.activeCollection || undefined
      const res = await ragApi.triggerIngest({ force_reingest: force }, col)
      message.value = res.message
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Error al iniciar ingestión'
    } finally {
      loading.value = false
    }
  }

  return { loading, message, error, ingest }
}

// ── Query ────────────────────────────────────────────────────
export function useQuery() {
  const collectionStore = useCollectionStore()
  const loading = ref(false)
  const result = ref<QueryResponse | null>(null)
  const error = ref<string | null>(null)

  async function query(q: string, topK = 3) {
    loading.value = true
    result.value = null
    error.value = null
    try {
      const col = collectionStore.activeCollection || undefined
      result.value = await ragApi.queryRag({ query: q, top_k: topK }, col)
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      error.value = typeof detail === 'string' ? detail : 'Error al consultar el RAG'
    } finally {
      loading.value = false
    }
  }

  return { loading, result, error, query }
}

// ── Ingest Status ─────────────────────────────────────────────
/**
 * Consulta GET /ingest/status?collection=... cada 3s mientras status === 'running'.
 * Se detiene automáticamente al completarse o fallar.
 */
export function useIngestStatus() {
  const collectionStore = useCollectionStore()
  const ingestStatus = ref<IngestStatus>({
    status: 'idle',
    message: 'Sin ingestión previa.',
    started_at: null,
    finished_at: null,
  })

  const { pause, resume, isActive } = useIntervalFn(
    async () => {
      try {
        const col = collectionStore.activeCollection || undefined
        ingestStatus.value = await ragApi.getIngestStatus(col)
        if (ingestStatus.value.status !== 'running') {
          pause()
        }
      } catch {
        pause()
      }
    },
    3_000,
    { immediate: false },
  )

  /** Llama a esto tras disparar /ingest para iniciar el polling. */
  function startPolling() {
    resume()
  }

  return { ingestStatus, startPolling, isPolling: isActive }
}

// ── Reset ────────────────────────────────────────────────────
export function useReset() {
  const loading = ref(false)
  const message = ref<string | null>(null)
  const error = ref<string | null>(null)

  async function reset() {
    loading.value = true
    message.value = null
    error.value = null
    try {
      const res = await ragApi.resetCollection()
      message.value = res.message
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Error al resetear colección'
    } finally {
      loading.value = false
    }
  }

  return { loading, message, error, reset }
}

// ── Chat multi-turn ───────────────────────────────────────────────────────────
export function useChat() {
  const collectionStore = useCollectionStore()
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)
  const streaming = ref(false)
  const streamingText = ref('')
  const error = ref<RagStreamError | null>(null)
  const topK = ref(3)
  const fileTypeFilter = ref<string | null>(null)

  const STORAGE_KEY_MESSAGES = 'rag_chat_messages'
  const STORAGE_KEY_SESSION  = 'rag_chat_session_id'

  // Carga inicial desde localStorage
  const stored = localStorage.getItem(STORAGE_KEY_MESSAGES)
  if (stored) {
    try { messages.value = JSON.parse(stored) } catch { messages.value = [] }
  }
  const storedSession = localStorage.getItem(STORAGE_KEY_SESSION)
  const sessionId = ref(storedSession ?? crypto.randomUUID())
  if (!storedSession) localStorage.setItem(STORAGE_KEY_SESSION, sessionId.value)

  // Persistir en cada cambio
  watchEffect(() => {
    localStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify(messages.value.slice(-50)))
  })
  watchEffect(() => {
    if (sessionId.value)
      localStorage.setItem(STORAGE_KEY_SESSION, sessionId.value)
  })

  async function send(message: string) {
    if (!message.trim() || loading.value || streaming.value) return

    messages.value.push({
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: Date.now(),
    })

    streaming.value = true
    streamingText.value = ''
    error.value = null

    const col = collectionStore.activeCollection || undefined

    await ragApi.chatStream(
      { message, session_id: sessionId.value, top_k: topK.value, file_type_filter: fileTypeFilter.value || null } as ChatRequest,
      (token) => { streamingText.value += token },
      (data) => {
        messages.value.push({
          id: data.query_id,
          role: 'assistant',
          content: streamingText.value,
          sources: data.sources as SourceInfo[],
          nodes_retrieved: data.nodes_retrieved,
          query_id: data.query_id,
          timestamp: Date.now(),
        })
        streamingText.value = ''
        streaming.value = false
        loading.value = false
      },
      () => {
        // onDone — si sources no llegó, cerrar igual
        if (streaming.value) {
          messages.value.push({
            id: crypto.randomUUID(),
            role: 'assistant',
            content: streamingText.value,
            timestamp: Date.now(),
          })
          streamingText.value = ''
          streaming.value = false
          loading.value = false
        }
      },
      (err) => {
        error.value = err
        streamingText.value = ''
        streaming.value = false
        loading.value = false
      },
      col,
    )
  }

  async function clearSession() {
    try { await ragApi.clearChatSession(sessionId.value) } catch { /* ignorar */ }
    messages.value = []
    error.value = null
    localStorage.removeItem(STORAGE_KEY_MESSAGES)
    localStorage.removeItem(STORAGE_KEY_SESSION)
  }

  async function submitFeedback(msg: ChatMessage, rating: 1 | -1) {
    if (!msg.query_id) return
    const idx = messages.value.findIndex(m => m.id === msg.id)
    const userMsg = idx > 0 ? messages.value[idx - 1] : null
    msg.rating = rating
    try {
      await ragApi.submitFeedback({
        query_id: msg.query_id,
        query: userMsg?.content ?? '',
        answer: msg.content,
        rating,
      })
    } catch { /* ignorar */ }
  }

  function exportMarkdown() {
    const lines: string[] = ['# Conversación RAG\n', `> Exportada el ${new Date().toLocaleString('es-AR')}\n`]
    for (const msg of messages.value) {
      if (msg.role === 'user') {
        lines.push(`\n**👤 Tú:**\n\n${msg.content}\n`)
      } else {
        lines.push(`\n**🤖 RAG:**\n\n${msg.content}\n`)
        if (msg.sources?.length) {
          lines.push('\n**Fuentes:** ' + msg.sources.map(s => s.filename).join(', ') + '\n')
        }
      }
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `conversacion-rag-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return {
    messages,
    loading,
    streaming,
    streamingText,
    error,
    topK,
    fileTypeFilter,
    sessionId,
    send,
    clearSession,
    submitFeedback,
    exportMarkdown,
  }
}
