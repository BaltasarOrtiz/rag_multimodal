import { ref, computed } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import ragApi from '@/api/ragApi'
import { useCollectionStore } from '@/stores/useCollectionStore'
import { useConversationStore } from '@/stores/useConversationStore'
import type { QueryResponse, DocumentInfo, IngestStatus, ChatMessage, SourceInfo, RagStreamError, ChatRequest } from '@/types/rag'

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
  const convStore = useConversationStore()

  const loading = ref(false)
  const streaming = ref(false)
  const streamingText = ref('')
  const error = ref<RagStreamError | null>(null)
  const topK = ref(3)
  const fileTypeFilter = ref<string | null>(null)

  // Las messages y el sessionId viven en el store
  const messages = computed(() => convStore.activeConversation?.messages ?? [])
  const sessionId = computed(() => convStore.activeConversation?.sessionId ?? '')

  async function send(message: string) {
    if (!message.trim() || loading.value || streaming.value) return

    const convId = convStore.activeId
    if (!convId) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: Date.now(),
    }
    convStore.addMessage(convId, userMsg)

    // Agregar burbuja de asistente vacía para actualizar luego
    const assistantMsgId = crypto.randomUUID()
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    }
    convStore.addMessage(convId, assistantMsg)

    streaming.value = true
    streamingText.value = ''
    error.value = null

    const col = collectionStore.activeCollection || undefined

    await ragApi.chatStream(
      { message, session_id: sessionId.value, top_k: topK.value, file_type_filter: fileTypeFilter.value || null } as ChatRequest,
      (token) => {
        streamingText.value += token
        // Actualizar el mensaje del asistente en el store en tiempo real
        convStore.updateLastAssistantMessage(convId, streamingText.value)
      },
      (data) => {
        convStore.updateLastAssistantMessage(convId, streamingText.value, data.sources as SourceInfo[])
        // Actualizar query_id y nodes_retrieved en el último mensaje del asistente
        const conv = convStore.activeConversation
        if (conv) {
          const lastAssistant = [...conv.messages].reverse().find(m => m.role === 'assistant')
          if (lastAssistant) {
            lastAssistant.query_id = data.query_id
            lastAssistant.nodes_retrieved = data.nodes_retrieved
          }
        }
        streamingText.value = ''
        streaming.value = false
        loading.value = false
      },
      () => {
        // onDone — si sources no llegó, cerrar igual
        if (streaming.value) {
          convStore.updateLastAssistantMessage(convId, streamingText.value)
          streamingText.value = ''
          streaming.value = false
          loading.value = false
        }
      },
      (err) => {
        error.value = err
        // Eliminar el mensaje de asistente vacío si hubo error
        convStore.deleteMessage(convId, assistantMsgId)
        streamingText.value = ''
        streaming.value = false
        loading.value = false
      },
      col,
    )
  }

  async function clearSession() {
    const convId = convStore.activeId
    if (convId) {
      try { await ragApi.clearChatSession(sessionId.value) } catch { /* ignorar */ }
    }
    error.value = null
    convStore.createConversation()
  }

  async function submitFeedback(msg: ChatMessage, rating: 1 | -1) {
    if (!msg.query_id) return
    const msgs = messages.value
    const idx = msgs.findIndex(m => m.id === msg.id)
    const userMsg = idx > 0 ? msgs[idx - 1] : null
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

  function exportConversation(format: 'md' | 'html') {
    const { marked } = window as any
    const DOMPurify = (window as any).DOMPurify
    const title = convStore.activeConversation?.title ?? 'Conversación RAG'
    const now = new Date().toLocaleString('es-AR')

    if (format === 'md') {
      const lines: string[] = [`# ${title}\n`, `> Exportada el ${now}\n`]
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
      _downloadBlob(blob, `conversacion-rag-${Date.now()}.md`)
    } else {
      // HTML con estilos inline oscuros
      const msgHtml = messages.value.map(msg => {
        if (msg.role === 'user') {
          return `<div style="display:flex;justify-content:flex-end;margin:1rem 0">
            <div style="background:rgba(34,211,238,0.1);border:1px solid rgba(34,211,238,0.25);border-radius:12px;padding:0.875rem 1.125rem;max-width:75%;color:#e2e8f0;white-space:pre-wrap">${_escapeHtml(msg.content)}</div>
          </div>`
        } else {
          // Para HTML, usamos el contenido tal cual (ya es markdown; en HTML export lo renderizamos inline)
          const contentHtml = _parseMarkdownToHtml(msg.content)
          const sourcesHtml = msg.sources?.length
            ? `<div style="font-size:0.75rem;color:#94a3b8;margin-top:0.5rem">Fuentes: ${msg.sources.map(s => _escapeHtml(s.filename)).join(', ')}</div>`
            : ''
          return `<div style="display:flex;align-items:flex-start;gap:0.75rem;margin:1rem 0">
            <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:0.875rem 1.125rem;max-width:85%;color:#e2e8f0">${contentHtml}${sourcesHtml}</div>
          </div>`
        }
      }).join('\n')

      const html = `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${_escapeHtml(title)}</title>
<style>
  body { background: #0a0a0f; font-family: system-ui, -apple-system, sans-serif; color: #e2e8f0; margin: 0; padding: 2rem; }
  h1 { color: #22d3ee; font-size: 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 0.5rem; }
  .meta { color: #64748b; font-size: 0.875rem; margin-bottom: 2rem; }
  pre { background: rgba(0,0,0,0.4); border-radius: 8px; padding: 1em; overflow-x: auto; }
  code { font-family: monospace; }
  footer { color: #475569; font-size: 0.75rem; text-align: center; margin-top: 3rem; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 1rem; }
</style>
</head>
<body>
<h1>${_escapeHtml(title)}</h1>
<p class="meta">Exportada el ${now}</p>
${msgHtml}
<footer>RAG Multimodal · LlamaIndex · Gemini · Qdrant</footer>
</body>
</html>`
      const blob = new Blob([html], { type: 'text/html' })
      _downloadBlob(blob, `conversacion-rag-${Date.now()}.html`)
    }
  }

  // Alias para compatibilidad con código existente
  function exportMarkdown() { exportConversation('md') }

  function _downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  function _escapeHtml(str: string): string {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  }

  function _parseMarkdownToHtml(text: string): string {
    // Conversión básica para HTML export (sin dependencia de marked en runtime)
    return text
      .replace(/```[\s\S]*?```/g, m => `<pre><code>${_escapeHtml(m.slice(3, -3).replace(/^[a-z]+\n/, ''))}</code></pre>`)
      .replace(/`([^`]+)`/g, (_, c) => `<code>${_escapeHtml(c)}</code>`)
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      .replace(/\n/g, '<br>')
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
    exportConversation,
  }
}
