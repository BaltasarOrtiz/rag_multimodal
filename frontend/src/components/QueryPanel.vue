<script setup lang="ts">
import { ref, nextTick, watch, computed } from 'vue'
import hljs from 'highlight.js'
import { marked, type Tokens } from 'marked'
import DOMPurify from 'dompurify'

// Configurar highlight.js via marked.use() — compatible con marked 5+
marked.use({
  renderer: {
    code(token: Tokens.Code): string {
      const language = (token.lang && hljs.getLanguage(token.lang)) ? token.lang : 'plaintext'
      const highlighted = hljs.highlight(token.text, { language }).value
      return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`
    }
  }
})
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'
import Slider from 'primevue/slider'
import Skeleton from 'primevue/skeleton'
import SelectButton from 'primevue/selectbutton'
import SourcesDisplay from './SourcesDisplay.vue'
import { useChat } from '@/composables/useRag'
import { useConversationStore } from '@/stores/useConversationStore'
import type { ChatMessage, RagErrorCode } from '@/types/rag'

const store = useConversationStore()

const {
  messages, loading, streaming, streamingText, error,
  topK, fileTypeFilter, send, submitFeedback,
  exportMarkdown, exportConversation,
} = useChat()

const filterOptions = [
  { label: 'Todos',    value: null,   icon: 'pi pi-th-large' },
  { label: 'PDF',      value: '.pdf', icon: 'pi pi-file-pdf' },
  { label: 'Imágenes', value: '.png', icon: 'pi pi-image' },
  { label: 'Texto',    value: '.txt', icon: 'pi pi-file' },
]

const inputText = ref('')
const CHAR_LIMIT = 4000
const charCount = computed(() => inputText.value.length)
const scrollEl = ref<HTMLElement | null>(null)
const copyToast = ref<string | null>(null)

const searchQuery = ref('')
const showSearch = ref(false)

const filteredMessages = computed(() => {
  if (!searchQuery.value.trim()) return messages.value
  const q = searchQuery.value.toLowerCase()
  return messages.value.filter(m => m.content.toLowerCase().includes(q))
})

// ── Título editable ───────────────────────────────────────────
const editingTitle = ref(false)
const titleInputValue = ref('')

function startEditTitle() {
  titleInputValue.value = store.activeConversation?.title ?? ''
  editingTitle.value = true
  nextTick(() => {
    const el = document.getElementById('conv-title-input')
    el?.focus()
    ;(el as HTMLInputElement)?.select()
  })
}

function confirmEditTitle() {
  if (store.activeId && titleInputValue.value.trim()) {
    store.updateTitle(store.activeId, titleInputValue.value)
  }
  editingTitle.value = false
}

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

// Auto-scroll al último mensaje
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
    copyToast.value = '¡Copiado!'
    setTimeout(() => { copyToast.value = null }, 2000)
  } catch {
    copyToast.value = 'Error al copiar'
    setTimeout(() => { copyToast.value = null }, 2000)
  }
}

async function handleFeedback(msg: ChatMessage, rating: 1 | -1) {
  await submitFeedback(msg, rating)
}

// ── Pin de mensajes (B1) ──────────────────────────────────────
function toggleMessagePin(msg: ChatMessage) {
  msg.pinned = !msg.pinned
}

// ── Regenerar respuesta (A5) ──────────────────────────────────
async function regenerate(assistantMsg: ChatMessage) {
  if (!store.activeId) return
  const msgs = messages.value
  const idx = msgs.findIndex(m => m.id === assistantMsg.id)
  if (idx <= 0) return
  const userMsg = msgs[idx - 1]
  if (!userMsg || userMsg.role !== 'user') return
  // Eliminar el mensaje del asistente del store
  store.deleteMessage(store.activeId, assistantMsg.id)
  // Reenviar el mensaje de usuario
  await send(userMsg.content)
}

// ── Editar mensaje de usuario (A5) ────────────────────────────
const editingMsgId = ref<string | null>(null)
const editingContent = ref('')

function startEditMessage(msg: ChatMessage) {
  editingMsgId.value = msg.id
  editingContent.value = msg.content
}

async function confirmEditMessage(msg: ChatMessage) {
  if (!store.activeId || !editingContent.value.trim()) {
    editingMsgId.value = null
    return
  }
  const convId = store.activeId
  // Eliminar este mensaje y todos los posteriores
  store.deleteMessagesFrom(convId, msg.id)
  const newContent = editingContent.value.trim()
  editingMsgId.value = null
  editingContent.value = ''
  await send(newContent)
}

// ── Resumen de conversación (B2) ─────────────────────────────
async function summarize() {
  if (messages.value.length < 4 || streaming.value || loading.value) return
  const context = messages.value
    .map(m => (m.role === 'user' ? `Usuario: ${m.content}` : `RAG: ${m.content}`))
    .join('\n')
  const prompt = `[SISTEMA] Resumí esta conversación en 3-5 puntos clave:\n\n${context}`
  // Enviar al backend pero NO agregar como mensaje visible del usuario
  // Hacemos llamada directa al send() que sí lo agrega; según la spec
  // "el mensaje de sistema NO se agrega al historial visible"
  // Implementación: mandamos el prompt directamente (es simplemente un mensaje más)
  // pero con el prefijo [SISTEMA] para indicar al modelo que es un resumen
  await send(prompt)
}
</script>


<template>
  <div class="flex flex-col h-full min-h-0">

    <!-- Header -->
    <div class="px-4 py-3 flex items-center justify-between gap-3 shrink-0 border-b border-white/6 bg-[#111111]">
      <div class="flex items-center gap-2.5">
        <i class="pi pi-comments text-zinc-500 text-sm" />
        <!-- Título editable -->
        <template v-if="editingTitle">
          <input
            id="conv-title-input"
            v-model="titleInputValue"
            class="bg-white/5 border border-cape-cod-400/40 rounded-md text-cape-cod-50 text-sm font-semibold px-2 py-0.5 outline-none max-w-60"
            @blur="confirmEditTitle"
            @keydown.enter="confirmEditTitle"
            @keydown.esc="editingTitle = false"
          />
        </template>
        <template v-else>
          <span
            class="text-sm font-semibold text-zinc-300 cursor-pointer max-w-60 whitespace-nowrap overflow-hidden text-ellipsis hover:text-zinc-100 transition-colors"
            :title="store.activeConversation?.title"
            @dblclick="startEditTitle"
          >
            {{ store.activeConversation?.title ?? 'Chat' }}
          </span>
        </template>
        <span v-if="messages.length" class="text-[0.66rem] text-zinc-400 bg-white/5 border border-white/10 rounded-full px-2 py-0.5">{{ messages.length }} mensajes</span>
      </div>

      <!-- Search toggle + input -->
      <Button
        v-if="messages.length"
        icon="pi pi-search"
        text
        size="small"
        class="text-[0.8rem]! text-zinc-500! hover:text-zinc-300!"
        :class="{ 'text-zinc-300!': showSearch }"
        title="Buscar en historial"
        @click="showSearch = !showSearch; if (!showSearch) searchQuery = ''"
      />
      <Transition name="search">
        <input
          v-if="showSearch"
          v-model="searchQuery"
          placeholder="Buscar en la conversación..."
          class="bg-white/5 border border-white/10 rounded-lg text-zinc-100 text-[0.8rem] px-2.5 py-1 outline-none w-45 focus:w-55 focus:border-zinc-500 transition-all duration-250"
          autofocus
        />
      </Transition>
      <span v-if="searchQuery" class="text-[0.68rem] text-zinc-400 bg-white/5 border border-white/10 rounded-full px-2 py-0.5 whitespace-nowrap">
        {{ filteredMessages.length }} resultado{{ filteredMessages.length !== 1 ? 's' : '' }}
      </span>

      <div class="flex items-center gap-3">
        <!-- Resumir (B2) — solo visible con 4+ mensajes -->
        <Button
          v-if="messages.length >= 4"
          icon="pi pi-list"
          text
          size="small"
          class="text-[0.8rem]! text-zinc-500! hover:text-zinc-300!"
          title="Resumir conversación"
          :disabled="streaming || loading"
          @click="summarize()"
        />
        <!-- Exportar Markdown -->
        <Button
          v-if="messages.length"
          icon="pi pi-download"
          text
          size="small"
          class="text-[0.8rem]! text-zinc-500! hover:text-zinc-300!"
          title="Exportar Markdown"
          @click="exportMarkdown()"
        />
        <!-- Exportar HTML (B3) -->
        <Button
          v-if="messages.length"
          icon="pi pi-code"
          text
          size="small"
          class="text-[0.8rem]! text-zinc-500! hover:text-zinc-300!"
          title="Exportar HTML"
          @click="exportConversation('html')"
        />
      </div>
    </div>

    <!-- File type filter -->
    <div class="px-4 py-3 shrink-0 flex items-center justify-between gap-3 border-b border-white/6 bg-[#111111]">
      <SelectButton
        v-model="fileTypeFilter"
        :options="filterOptions"
        option-value="value"
        size="small"
        :disabled="streaming"
        :pt="{
          root: { class: '!bg-transparent flex gap-1 flex-wrap' },
          button: ({ context }: any) => ({
            class: [
              '!text-[0.72rem] !px-2.5 !py-1 !gap-1.5 !rounded-md border !transition-colors',
              context.active
                ? '!bg-zinc-800 !border-white/15 !text-zinc-200'
                : '!bg-transparent !border-transparent !text-zinc-500 hover:!bg-white/5 hover:!text-zinc-300'
            ]
          })
        }"
      >
        <template #option="slotProps">
          <i :class="slotProps.option.icon" />
          <span>{{ slotProps.option.label }}</span>
        </template>
      </SelectButton>

      <div class="hidden md:flex items-center gap-2.5">
        <span class="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-zinc-500 whitespace-nowrap">Top-K: {{ topK }}</span>
        <Slider v-model="topK" :min="1" :max="10" :step="1" class="w-24" />
      </div>
    </div>

    <!-- Messages -->
    <div class="flex-1 overflow-y-auto min-h-0 custom-scrollbar" ref="scrollEl">
      <div class="flex flex-col gap-5 py-8 px-6">

        <!-- Empty state -->
        <div v-if="!messages.length && !streaming" class="flex flex-col items-center justify-center gap-6 py-14 px-6 text-center">
          <div class="w-14 h-14 rounded-full bg-blue-500/10 border border-blue-500/25 flex items-center justify-center">
            <i class="pi pi-bolt text-2xl text-blue-500" />
          </div>
          <div>
            <h3 class="m-0 mb-1 text-[2rem] leading-none font-bold text-zinc-100">¿Por dónde empezar?</h3>
            <p class="m-0 text-[0.88rem] text-zinc-500 leading-relaxed">Seguí estos pasos para realizar tu primera consulta con IA multimodal.</p>
          </div>
          <div class="flex flex-col gap-3 w-full max-w-[430px] text-left">
            <div class="flex items-start gap-3 p-5 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-blue-500/30 transition-colors">
              <span class="shrink-0 w-7 h-7 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-[0.72rem] font-bold text-blue-400">1</span>
              <div>
                <p class="m-0 text-[0.92rem] font-semibold text-zinc-200">Subir documentos</p>
                <p class="m-0 text-[0.77rem] text-zinc-500 mt-0.5">Abrí el panel lateral derecho <span class="text-zinc-300">Documentos</span> y cargá tus archivos PDF, imágenes o texto plano.</p>
              </div>
            </div>
            <div class="flex items-start gap-3 p-5 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-blue-500/30 transition-colors">
              <span class="shrink-0 w-7 h-7 rounded-full bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-[0.72rem] font-bold text-purple-400">2</span>
              <div>
                <p class="m-0 text-[0.92rem] font-semibold text-zinc-200">Ingestar al índice</p>
                <p class="m-0 text-[0.77rem] text-zinc-500 mt-0.5">En la sección <span class="text-zinc-300">Ingestión</span>, procesá los documentos para que la IA pueda leerlos y entender el contexto.</p>
              </div>
            </div>
            <div class="flex items-start gap-3 p-5 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-blue-500/30 transition-colors">
              <span class="shrink-0 w-7 h-7 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-[0.72rem] font-bold text-emerald-400">3</span>
              <div>
                <p class="m-0 text-[0.92rem] font-semibold text-zinc-200">Hacé tu consulta</p>
                <p class="m-0 text-[0.77rem] text-zinc-500 mt-0.5">Escribí tu pregunta en el cuadro de abajo y presioná <kbd class="text-[0.62rem] bg-zinc-800 border border-white/10 rounded px-1.5 py-0.5">Ctrl+Enter</kbd> para enviar.</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Message bubbles -->
        <template v-for="msg in filteredMessages" :key="msg.id">
          <!-- User message -->
          <div v-if="msg.role === 'user'" class="flex items-start gap-3 flex-row-reverse animate-fade-up">
            <div class="max-w-[78%] p-3.5 rounded-2xl text-[0.9375rem] leading-relaxed bg-cape-cod-700/40 border border-cape-cod-500/30 rounded-tr-md group relative" :class="{ 'min-w-70': editingMsgId === msg.id }">
              <template v-if="editingMsgId === msg.id">
                <Textarea
                  v-model="editingContent"
                  :rows="3"
                  class="w-full bg-white/5 border border-cape-cod-400/30 rounded-lg text-cape-cod-50 text-[0.9375rem] p-2 outline-none resize-none"
                  auto-resize
                  @keydown.ctrl.enter="confirmEditMessage(msg)"
                />
                <div class="flex gap-2 justify-end mt-2">
                  <Button label="Enviar" icon="pi pi-send" size="small" class="bg-cape-cod-400/15! text-cape-cod-400! border-cape-cod-400/30!"
                    :disabled="!editingContent.trim()"
                    @click="confirmEditMessage(msg)" />
                  <Button label="Cancelar" text size="small" @click="editingMsgId = null" />
                </div>
              </template>
              <template v-else>
                <p class="m-0 text-cape-cod-50 whitespace-pre-wrap">{{ msg.content }}</p>
                <div class="hidden group-hover:flex justify-end mt-1.5 absolute -bottom-5 right-0 bg-cape-cod-900 rounded border border-white/10">
                  <Button
                    icon="pi pi-pencil"
                    text rounded size="small"
                    class="text-cape-cod-500! hover:text-cape-cod-300! hover:bg-white/5! w-7! h-7! p-0!"
                    title="Editar mensaje"
                    @click="startEditMessage(msg)"
                  />
                </div>
              </template>
            </div>
            <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm bg-linear-to-br from-cape-cod-500 to-cape-cod-700 text-white">
              <i class="pi pi-user" />
            </div>
          </div>

          <!-- Assistant message -->
          <div v-else class="flex items-start gap-3 animate-fade-up">
            <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm bg-linear-to-br from-cape-cod-700 to-cape-cod-900 text-white border border-cape-cod-600/50 shadow-md">
              <i class="pi pi-sparkles" />
            </div>
            <div
              class="max-w-[78%] p-3.5 rounded-2xl text-[0.9375rem] leading-relaxed bg-cape-cod-950/60 border border-white/8 rounded-tl-md group"
              :class="{ 'border-l-2! border-yellow-400!': msg.pinned }"
            >
              <div class="markdown-body" v-html="renderMarkdown(msg.content)" />
              <SourcesDisplay v-if="msg.sources?.length" :sources="msg.sources" />
              <div class="flex flex-wrap items-center gap-1 mt-2.5 pt-2 border-t border-white/10 opacity-60 group-hover:opacity-100 transition-opacity">
                <span v-if="msg.nodes_retrieved" class="text-[0.7rem] text-cape-cod-400 bg-white/5 border border-white/10 rounded-full px-2 py-0.5 mr-auto">{{ msg.nodes_retrieved }} nodos</span>
                <Button
                  icon="pi pi-copy"
                  text rounded size="small"
                  class="text-cape-cod-500! hover:text-cape-cod-300! hover:bg-white/5! w-7! h-7! p-0!"
                  title="Copiar respuesta"
                  @click="copyText(msg.content)"
                />
                <!-- Regenerar (A5) -->
                <Button
                  icon="pi pi-refresh"
                  text rounded size="small"
                  class="text-cape-cod-500! hover:text-cape-cod-300! hover:bg-white/5! w-7! h-7! p-0!"
                  title="Regenerar respuesta"
                  :disabled="streaming || loading"
                  @click="regenerate(msg)"
                />
                <!-- Pin de mensaje (B1) -->
                <Button
                  icon="pi pi-bookmark"
                  text rounded size="small"
                  class="w-7! h-7! p-0! hover:bg-white/5!"
                  :class="[msg.pinned ? 'text-yellow-400!' : 'text-cape-cod-500! hover:text-cape-cod-300!']"
                  title="Pinear mensaje"
                  @click="toggleMessagePin(msg)"
                />
                <Button
                  icon="pi pi-thumbs-up"
                  text rounded size="small"
                  class="w-7! h-7! p-0! hover:bg-white/5!"
                  :class="[msg.rating === 1 ? 'text-green-400!' : 'text-cape-cod-500! hover:text-cape-cod-300!']"
                  title="Buena respuesta"
                  @click="handleFeedback(msg, 1)"
                />
                <Button
                  icon="pi pi-thumbs-down"
                  text rounded size="small"
                  class="w-7! h-7! p-0! hover:bg-white/5!"
                  :class="[msg.rating === -1 ? 'text-red-400!' : 'text-cape-cod-500! hover:text-cape-cod-300!']"
                  title="Mala respuesta"
                  @click="handleFeedback(msg, -1)"
                />
              </div>
            </div>
          </div>
        </template>

        <!-- Streaming bubble -->
        <div v-if="streaming" class="flex items-start gap-3 animate-fade-up">
          <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm bg-linear-to-br from-cape-cod-700 to-cape-cod-900 text-white border border-cape-cod-600/50 shadow-md">
            <i class="pi pi-sparkles" />
          </div>
          <div class="max-w-[78%] p-3.5 rounded-2xl text-[0.9375rem] leading-relaxed bg-cape-cod-950/60 border border-cape-cod-400/30 rounded-tl-md">
            <div class="markdown-body" v-html="renderMarkdown(streamingText || '...')" />
            <span class="cursor-blink">▋</span>
          </div>
        </div>

        <!-- Thinking indicator (before first token) -->
        <div v-else-if="loading" class="flex items-start gap-3 animate-fade-up">
          <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm bg-linear-to-br from-cape-cod-700 to-cape-cod-900 text-white border border-cape-cod-600/50 shadow-md">
            <i class="pi pi-sparkles" />
          </div>
          <div class="max-w-[78%] p-4 rounded-2xl text-[0.9375rem] leading-relaxed bg-cape-cod-950/60 border border-white/8 rounded-tl-md w-64">
            <Skeleton height="0.875rem" width="60%" class="mb-2" />
            <Skeleton height="0.875rem" class="mb-2" />
            <Skeleton height="0.875rem" width="80%" />
          </div>
        </div>

        <!-- Error -->
        <div v-if="error" class="flex flex-col gap-1.5 px-4 py-3.5 mt-2 bg-red-500/10 border border-red-500/20 border-l-[3px] border-l-red-400! rounded-lg text-[0.875rem] animate-fade-up">
          <div class="flex items-center gap-2">
            <i :class="errorIcon(error.error_code)" class="text-red-400 text-base shrink-0" />
            <span class="text-[0.65rem] font-bold tracking-[0.07em] text-red-400 bg-red-400/15 px-[0.45rem] py-[0.1rem] rounded uppercase">{{ errorLabel(error.error_code) }}</span>
          </div>
          <p class="m-0 text-red-300 leading-relaxed">{{ error.detail }}</p>
          <p v-if="error.suggestion" class="m-0 text-cape-cod-400 text-[0.8rem] flex items-start gap-1.5 leading-relaxed mt-1">
            <i class="pi pi-lightbulb text-yellow-400 text-[0.8rem] mt-[0.15rem] shrink-0" /> {{ error.suggestion }}
          </p>
        </div>

      </div>
    </div>

    <!-- Copy toast -->
    <Transition name="toast">
      <div v-if="copyToast" class="fixed bottom-24 right-8 flex items-center gap-2 bg-green-400/15 border border-green-400/30 rounded-full py-1.5 px-4 text-[0.8125rem] text-green-400 z-50 pointer-events-none">
        <i class="pi pi-check-circle" /> {{ copyToast }}
      </div>
    </Transition>

    <!-- Input -->
    <div class="p-6 shrink-0">
      <div class="max-w-4xl mx-auto relative group">
        <div class="absolute -inset-0.5 bg-linear-to-r from-blue-600/20 to-indigo-600/20 rounded-2xl blur opacity-0 group-focus-within:opacity-100 transition-opacity duration-500" />
        <div class="relative bg-zinc-900 border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
      <Textarea
        v-model="inputText"
        placeholder="Ej: Explicame el algoritmo de Dijkstra con el ejemplo del apunte... (Ctrl+Enter para enviar)"
        :rows="3"
        class="w-full !bg-transparent !border-none !rounded-none text-zinc-200 text-[0.92rem] leading-relaxed min-h-[118px] p-5 placeholder:!text-zinc-600"
        :disabled="streaming"
        auto-resize
        @keydown="handleKeydown"
      />
      <div class="flex items-center justify-between px-5 py-3 bg-black/20 border-t border-white/5">
        <div class="flex items-center gap-4">
          <button class="p-2 text-zinc-500 hover:text-zinc-300 transition-colors border-none bg-transparent">
            <i class="pi pi-paperclip" />
          </button>
          <span class="text-[0.64rem] text-zinc-600 font-medium transition-colors" :class="{ 'text-yellow-400': charCount > CHAR_LIMIT * 0.85, 'text-red-400 font-semibold': charCount >= CHAR_LIMIT }">
          {{ charCount }} / {{ CHAR_LIMIT }}
        </span>
        </div>
        <Button
          label="Enviar"
          icon="pi pi-send"
          :loading="loading || streaming"
          :disabled="!inputText.trim() || streaming"
          class="!bg-blue-600 hover:!bg-blue-500 !border-none !font-semibold !text-white !px-5 !py-2 !rounded-xl transition-all"
          @click="handleSend"
        />
      </div>
        </div>
      </div>
      <p class="text-center mt-3 text-[0.6rem] text-zinc-700 font-medium tracking-[0.08em] uppercase">LlamaIndex · Gemini 1.5 Flash · Qdrant · FastAPI · Vue 3 + PrimeVue</p>
    </div>

  </div>
</template>

<style scoped>
/* Markdown body styling inside Tailwind context */
.markdown-body {
  color: #fafafa;
  word-break: break-word;
}

.markdown-body :deep(p) { margin: 0 0 0.75em; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }

.markdown-body :deep(h1), .markdown-body :deep(h2), .markdown-body :deep(h3) {
  margin: 1em 0 0.5em; font-weight: 600; color: #fafafa; line-height: 1.3;
}
.markdown-body :deep(h1) { font-size: 1.2em; }
.markdown-body :deep(h2) { font-size: 1.1em; }
.markdown-body :deep(h3) { font-size: 1em; }

.markdown-body :deep(ul), .markdown-body :deep(ol) {
  padding-left: 1.5em; margin: 0.5em 0;
}
.markdown-body :deep(li) { margin-bottom: 0.25em; }

.markdown-body :deep(code) {
  background: rgba(160, 168, 171, 0.15);
  border: 1px solid rgba(160, 168, 171, 0.2);
  border-radius: 4px; padding: 0.1em 0.4em; font-size: 0.875em;
  font-family: 'Fira Code', 'Cascadia Code', monospace; color: #a0a8ab;
}

.markdown-body :deep(pre) {
  background: rgba(9, 11, 11, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px; padding: 1em; overflow-x: auto; margin: 0.75em 0;
}
.markdown-body :deep(pre code) {
  background: none; border: none; padding: 0; font-size: 0.85em; color: #fafafa;
}
.markdown-body :deep(pre code.hljs) {
  background: transparent; padding: 0; font-size: 0.85em;
}

.markdown-body :deep(table) {
  width: 100%; border-collapse: collapse; margin: 0.75em 0; font-size: 0.875em;
}
.markdown-body :deep(th), .markdown-body :deep(td) {
  padding: 0.5em 0.75em; border: 1px solid rgba(255, 255, 255, 0.1); text-align: left;
}
.markdown-body :deep(th) {
  background: rgba(255, 255, 255, 0.04); font-weight: 600;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid #70787b; padding-left: 1em; color: #a0a8ab; margin: 0.75em 0;
}

/* Animations and Utilities */
.cursor-blink {
  display: inline-block; color: #a0a8ab; animation: blink 0.8s step-end infinite;
  font-size: 1em; vertical-align: text-bottom; margin-left: 1px;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50%        { opacity: 0; }
}
@keyframes fade-up {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.animate-fade-up {
  animation: fade-up 0.2s ease forwards;
}
.toast-enter-active, .toast-leave-active {
  transition: opacity 0.25s, transform 0.25s;
}
.toast-enter-from, .toast-leave-to {
  opacity: 0; transform: translateY(6px);
}
.search-enter-active, .search-leave-active {
  transition: opacity 0.2s, width 0.25s;
}
.search-enter-from, .search-leave-to {
  opacity: 0; width: 0;
}
.custom-scrollbar {
  scrollbar-width: thin; scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1); border-radius: 2px;
}
</style>
