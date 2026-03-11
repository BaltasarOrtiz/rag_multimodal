<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'
import Slider from 'primevue/slider'
import Skeleton from 'primevue/skeleton'
import SourcesDisplay from './SourcesDisplay.vue'
import { useChat } from '@/composables/useRag'
import type { ChatMessage, RagErrorCode } from '@/types/rag'

const {
  messages, loading, streaming, streamingText, error,
  topK, send, clearSession, submitFeedback, exportMarkdown,
} = useChat()

const inputText = ref('')
const scrollEl = ref<HTMLElement | null>(null)
const copyToast = ref<string | null>(null)

/** Icono PrimeVue según el código de error */
function errorIcon(code: RagErrorCode | undefined): string {
  switch (code) {
    case 'qdrant_not_found':    return 'pi pi-database'
    case 'qdrant_unavailable':  return 'pi pi-server'
    case 'qdrant_error':        return 'pi pi-database'
    case 'llm_quota':           return 'pi pi-clock'
    case 'llm_auth':            return 'pi pi-lock'
    case 'llm_unavailable':     return 'pi pi-cloud'
    case 'llm_timeout':         return 'pi pi-hourglass'
    case 'llm_error':           return 'pi pi-bolt'
    case 'hybrid_config':       return 'pi pi-sliders-h'
    case 'connection_error':    return 'pi pi-wifi'
    case 'timeout':             return 'pi pi-hourglass'
    default:                    return 'pi pi-exclamation-triangle'
  }
}

/** Etiqueta breve del código de error para el badge */
function errorLabel(code: RagErrorCode | undefined): string {
  const map: Record<RagErrorCode, string> = {
    qdrant_not_found:   'COLECCIÓN NO ENCONTRADA',
    qdrant_unavailable: 'QDRANT NO DISPONIBLE',
    qdrant_error:       'ERROR DE QDRANT',
    llm_quota:          'CUOTA AGOTADA',
    llm_auth:           'CREDENCIAL INVÁLIDA',
    llm_unavailable:    'API NO DISPONIBLE',
    llm_timeout:        'TIEMPO AGOTADO',
    llm_error:          'ERROR DEL LLM',
    hybrid_config:      'CONFIG. HÍBRIDA',
    connection_error:   'ERROR DE RED',
    timeout:            'TIEMPO AGOTADO',
    unknown:            'ERROR DESCONOCIDO',
  }
  return code ? (map[code] ?? 'ERROR') : 'ERROR'
}

// Renderizar Markdown de forma segura
function renderMarkdown(text: string): string {
  return DOMPurify.sanitize(marked.parse(text) as string)
}

// Auto-scroll al Ãºltimo mensaje
async function scrollToBottom() {
  await nextTick()
  if (scrollEl.value) {
    scrollEl.value.scrollTop = scrollEl.value.scrollHeight
  }
}

watch([() => messages.value.length, streamingText], scrollToBottom)

async function handleSend() {
  const msg = inputText.value.trim()
  if (!msg || streaming.value) return
  inputText.value = ''
  await send(msg)
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    handleSend()
  }
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    copyToast.value = 'Â¡Copiado!'
    setTimeout(() => { copyToast.value = null }, 2000)
  } catch {
    copyToast.value = 'Error al copiar'
    setTimeout(() => { copyToast.value = null }, 2000)
  }
}

async function handleFeedback(msg: ChatMessage, rating: 1 | -1) {
  await submitFeedback(msg, rating)
}

async function handleNewChat() {
  await clearSession()
  inputText.value = ''
}
</script>

<template>
  <div class="chat-panel">

    <!-- Header -->
    <div class="chat-header glass-card">
      <div class="header-left">
        <i class="pi pi-comments" />
        <span class="header-title">Chat RAG</span>
        <span v-if="messages.length" class="msg-count">{{ messages.length }} mensajes</span>
      </div>
      <div class="header-right">
        <div class="topk-control">
          <span class="topk-label">Top-K: <strong>{{ topK }}</strong></span>
          <Slider v-model="topK" :min="1" :max="10" :step="1" class="topk-slider" />
        </div>
        <Button
          v-if="messages.length"
          icon="pi pi-download"
          label="Exportar"
          text
          size="small"
          class="action-btn"
          @click="exportMarkdown"
        />
        <Button
          icon="pi pi-refresh"
          label="Nuevo chat"
          text
          size="small"
          class="action-btn"
          @click="handleNewChat"
        />
      </div>
    </div>

    <!-- Messages -->
    <div class="messages-scroll" ref="scrollEl">
      <div class="messages-container">

        <!-- Empty state -->
        <div v-if="!messages.length && !streaming" class="empty-state">
          <div class="empty-icon">
            <i class="pi pi-sparkles" />
          </div>
          <h3>ComenzÃ¡ la conversaciÃ³n</h3>
          <p>El RAG buscarÃ¡ en tus documentos y responderÃ¡ con contexto de mÃºltiples turnos.</p>
          <div class="hints">
            <span class="hint-chip"><i class="pi pi-history" /> Memoria de conversaciÃ³n</span>
            <span class="hint-chip"><i class="pi pi-bolt" /> Streaming en tiempo real</span>
            <span class="hint-chip"><i class="pi pi-file-edit" /> Markdown renderizado</span>
          </div>
        </div>

        <!-- Message bubbles -->
        <template v-for="msg in messages" :key="msg.id">
          <!-- User message -->
          <div v-if="msg.role === 'user'" class="message-row user-row">
            <div class="bubble user-bubble">
              <p class="user-text">{{ msg.content }}</p>
            </div>
            <div class="avatar user-avatar">
              <i class="pi pi-user" />
            </div>
          </div>

          <!-- Assistant message -->
          <div v-else class="message-row assistant-row">
            <div class="avatar assistant-avatar">
              <i class="pi pi-sparkles" />
            </div>
            <div class="bubble assistant-bubble">
              <div class="markdown-body" v-html="renderMarkdown(msg.content)" />
              <SourcesDisplay v-if="msg.sources?.length" :sources="msg.sources" />
              <div class="message-actions">
                <span v-if="msg.nodes_retrieved" class="nodes-badge">{{ msg.nodes_retrieved }} nodos</span>
                <Button
                  icon="pi pi-copy"
                  text
                  rounded
                  size="small"
                  class="action-icon"
                  title="Copiar respuesta"
                  @click="copyText(msg.content)"
                />
                <Button
                  icon="pi pi-thumbs-up"
                  text
                  rounded
                  size="small"
                  :class="['action-icon', { 'feedback-active-up': msg.rating === 1 }]"
                  title="Buena respuesta"
                  @click="handleFeedback(msg, 1)"
                />
                <Button
                  icon="pi pi-thumbs-down"
                  text
                  rounded
                  size="small"
                  :class="['action-icon', { 'feedback-active-down': msg.rating === -1 }]"
                  title="Mala respuesta"
                  @click="handleFeedback(msg, -1)"
                />
              </div>
            </div>
          </div>
        </template>

        <!-- Streaming bubble -->
        <div v-if="streaming" class="message-row assistant-row">
          <div class="avatar assistant-avatar">
            <i class="pi pi-sparkles" />
          </div>
          <div class="bubble assistant-bubble streaming-bubble">
            <div class="markdown-body" v-html="renderMarkdown(streamingText || '...')" />
            <span class="cursor-blink">â–‹</span>
          </div>
        </div>

        <!-- Thinking indicator (before first token) -->
        <div v-else-if="loading" class="message-row assistant-row">
          <div class="avatar assistant-avatar">
            <i class="pi pi-sparkles" />
          </div>
          <div class="bubble assistant-bubble thinking-bubble">
            <Skeleton height="0.875rem" width="60%" class="mb-2" />
            <Skeleton height="0.875rem" class="mb-2" />
            <Skeleton height="0.875rem" width="80%" />
          </div>
        </div>

        <!-- Error -->
        <div v-if="error" class="error-toast animate-in">
          <div class="error-header">
            <i :class="errorIcon(error.error_code)" class="error-icon" />
            <span class="error-badge">{{ errorLabel(error.error_code) }}</span>
          </div>
          <p class="error-detail">{{ error.detail }}</p>
          <p v-if="error.suggestion" class="error-suggestion">
            <i class="pi pi-lightbulb" /> {{ error.suggestion }}
          </p>
        </div>

      </div>
    </div>

    <!-- Copy toast -->
    <Transition name="toast">
      <div v-if="copyToast" class="copy-toast">
        <i class="pi pi-check-circle" /> {{ copyToast }}
      </div>
    </Transition>

    <!-- Input -->
    <div class="input-area glass-card">
      <Textarea
        v-model="inputText"
        placeholder="Ej: Explicame el algoritmo de Dijkstra con el ejemplo del apunte... (Ctrl+Enter para enviar)"
        :rows="3"
        class="chat-textarea"
        :disabled="streaming"
        auto-resize
        @keydown="handleKeydown"
      />
      <div class="input-footer">
        <span class="hint">
          <i class="pi pi-info-circle" /> Ctrl + Enter
        </span>
        <Button
          label="Enviar"
          icon="pi pi-send"
          :loading="loading || streaming"
          :disabled="!inputText.trim() || streaming"
          class="send-btn"
          @click="handleSend"
        />
      </div>
    </div>

  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: 100%;
  min-height: 0;
}

/* Header */
.chat-header {
  padding: 0.875rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.header-left i {
  color: var(--cyan-400);
  font-size: 1rem;
}

.header-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.msg-count {
  font-size: 0.7rem;
  color: var(--text-muted);
  background: rgba(34, 211, 238, 0.1);
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 9999px;
  padding: 0.125rem 0.5rem;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.topk-control {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.topk-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.topk-label strong {
  color: var(--cyan-400);
}

.topk-slider {
  width: 72px;
}

.action-btn {
  font-size: 0.8rem !important;
  color: var(--text-muted) !important;
}

.action-btn:hover {
  color: var(--cyan-400) !important;
}

/* Messages scroll */
.messages-scroll {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  scrollbar-width: thin;
  scrollbar-color: var(--border-subtle) transparent;
}

.messages-scroll::-webkit-scrollbar {
  width: 4px;
}

.messages-scroll::-webkit-scrollbar-thumb {
  background: var(--border-subtle);
  border-radius: 2px;
}

.messages-container {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 1rem 0.5rem;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.875rem;
  padding: 3rem 1.5rem;
  text-align: center;
  color: var(--text-muted);
}

.empty-icon {
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(34,211,238,0.1), rgba(139,92,246,0.1));
  border: 1px solid rgba(34,211,238,0.15);
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-icon i {
  font-size: 1.5rem;
  color: var(--cyan-400);
}

.empty-state h3 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.empty-state p {
  margin: 0;
  font-size: 0.875rem;
  max-width: 26rem;
  line-height: 1.6;
}

.hints {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin-top: 0.25rem;
}

.hint-chip {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  padding: 0.25rem 0.625rem;
  background: rgba(139, 92, 246, 0.07);
  border: 1px solid rgba(139, 92, 246, 0.18);
  border-radius: 9999px;
  color: var(--violet-400);
}

/* Message rows */
.message-row {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  animation: fadeUp 0.2s ease;
}

.user-row {
  flex-direction: row-reverse;
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Avatars */
.avatar {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 0.875rem;
}

.user-avatar {
  background: linear-gradient(135deg, var(--cyan-700), var(--cyan-500));
  color: #fff;
}

.assistant-avatar {
  background: linear-gradient(135deg, var(--violet-700), var(--violet-500));
  color: #fff;
}

/* Bubbles */
.bubble {
  max-width: 78%;
  padding: 0.875rem 1.125rem;
  border-radius: 1rem;
  font-size: 0.9375rem;
  line-height: 1.65;
}

.user-bubble {
  background: linear-gradient(135deg, rgba(34,211,238,0.12), rgba(34,211,238,0.06));
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-top-right-radius: 0.25rem;
}

.user-text {
  margin: 0;
  color: var(--text-primary);
  white-space: pre-wrap;
}

.assistant-bubble {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-subtle);
  border-top-left-radius: 0.25rem;
}

.streaming-bubble {
  border-color: rgba(139, 92, 246, 0.3);
}

.thinking-bubble {
  padding: 1rem 1.25rem;
}

/* Markdown body */
.markdown-body {
  color: var(--text-primary);
  word-break: break-word;
}

.markdown-body :deep(p) {
  margin: 0 0 0.75em;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 1em 0 0.5em;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.markdown-body :deep(h1) { font-size: 1.2em; }
.markdown-body :deep(h2) { font-size: 1.1em; }
.markdown-body :deep(h3) { font-size: 1em; }

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.markdown-body :deep(li) {
  margin-bottom: 0.25em;
}

.markdown-body :deep(code) {
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 4px;
  padding: 0.1em 0.4em;
  font-size: 0.875em;
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  color: var(--violet-300, #c4b5fd);
}

.markdown-body :deep(pre) {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 1em;
  overflow-x: auto;
  margin: 0.75em 0;
}

.markdown-body :deep(pre code) {
  background: none;
  border: none;
  padding: 0;
  font-size: 0.85em;
  color: var(--text-primary);
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.75em 0;
  font-size: 0.875em;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 0.5em 0.75em;
  border: 1px solid var(--border-subtle);
  text-align: left;
}

.markdown-body :deep(th) {
  background: rgba(255,255,255,0.04);
  font-weight: 600;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--cyan-500);
  padding-left: 1em;
  color: var(--text-muted);
  margin: 0.75em 0;
}

/* Streaming cursor */
.cursor-blink {
  display: inline-block;
  color: var(--violet-400);
  animation: blink 0.8s step-end infinite;
  font-size: 1em;
  vertical-align: text-bottom;
  margin-left: 1px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%        { opacity: 0; }
}

/* Message actions */
.message-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.625rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-subtle);
}

.nodes-badge {
  font-size: 0.7rem;
  color: var(--text-muted);
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border-subtle);
  border-radius: 9999px;
  padding: 0.1rem 0.5rem;
  margin-right: auto;
}

.action-icon {
  color: var(--text-muted) !important;
  width: 1.75rem !important;
  height: 1.75rem !important;
  padding: 0 !important;
}

.action-icon:hover {
  color: var(--text-secondary) !important;
  background: rgba(255,255,255,0.06) !important;
}

.feedback-active-up {
  color: #4ade80 !important;
}

.feedback-active-down {
  color: #f87171 !important;
}

/* Error */
.error-toast {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.875rem 1rem;
  background: rgba(239, 68, 68, 0.07);
  border: 1px solid rgba(239, 68, 68, 0.22);
  border-left: 3px solid #f87171;
  border-radius: 10px;
  font-size: 0.875rem;
}

.error-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.error-icon {
  color: #f87171;
  font-size: 1rem;
  flex-shrink: 0;
}

.error-badge {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  color: #f87171;
  background: rgba(239, 68, 68, 0.15);
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  text-transform: uppercase;
}

.error-detail {
  margin: 0;
  color: #fca5a5;
  line-height: 1.5;
}

.error-suggestion {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.8rem;
  display: flex;
  align-items: flex-start;
  gap: 0.35rem;
  line-height: 1.4;
}

.error-suggestion .pi {
  color: #fbbf24;
  font-size: 0.8rem;
  margin-top: 0.15rem;
  flex-shrink: 0;
}

/* Copy toast */
.copy-toast {
  position: fixed;
  bottom: 6rem;
  right: 2rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(74, 222, 128, 0.15);
  border: 1px solid rgba(74, 222, 128, 0.3);
  border-radius: 9999px;
  padding: 0.4rem 1rem;
  font-size: 0.8125rem;
  color: #4ade80;
  z-index: 100;
  pointer-events: none;
}

.toast-enter-active, .toast-leave-active {
  transition: opacity 0.25s, transform 0.25s;
}

.toast-enter-from, .toast-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

/* Input area */
.input-area {
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  flex-shrink: 0;
}

.chat-textarea {
  width: 100%;
  background: rgba(255, 255, 255, 0.03) !important;
  border: 1px solid var(--border-subtle) !important;
  border-radius: 10px !important;
  color: var(--text-primary) !important;
  font-size: 0.9375rem !important;
  line-height: 1.6 !important;
  transition: border-color 0.2s;
  resize: none !important;
}

.chat-textarea:focus {
  border-color: var(--cyan-500) !important;
  box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.08) !important;
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.send-btn {
  background: linear-gradient(135deg, var(--cyan-600), var(--violet-600)) !important;
  border: none !important;
  color: #fff !important;
  font-weight: 600 !important;
  padding: 0.5rem 1.25rem !important;
  border-radius: 8px !important;
  transition: opacity 0.2s, transform 0.1s !important;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.9 !important;
  transform: translateY(-1px) !important;
}

.animate-in {
  animation: fadeUp 0.25s ease;
}
</style>
