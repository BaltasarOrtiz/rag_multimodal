import { ref, computed, watchEffect } from 'vue'
import { defineStore } from 'pinia'
import type { ChatMessage, SourceInfo } from '@/types/rag'

// ── Tipos internos ────────────────────────────────────────────

interface Conversation {
  id: string
  title: string
  sessionId: string
  folderId: string | null
  createdAt: number
  updatedAt: number
  messages: ChatMessage[]
  pinned: boolean
}

interface Folder {
  id: string
  name: string
  color: string
  collapsed: boolean
}

// ── Colores disponibles para carpetas ────────────────────────

export const FOLDER_COLORS = [
  '#22d3ee', '#8b5cf6', '#4ade80', '#fb923c',
  '#f472b6', '#facc15', '#60a5fa', '#f87171',
]

// ── Claves localStorage ───────────────────────────────────────

const LS_CONVERSATIONS = 'rag_conversations'
const LS_FOLDERS = 'rag_folders'
const LS_ACTIVE = 'rag_active_conversation_id'

// ── Store ─────────────────────────────────────────────────────

export const useConversationStore = defineStore('conversations', () => {
  // ── Estado ────────────────────────────────────────────────

  function _loadLS<T>(key: string, fallback: T): T {
    try {
      const raw = localStorage.getItem(key)
      if (raw) return JSON.parse(raw) as T
    } catch { /* ignorar */ }
    return fallback
  }

  const conversations = ref<Conversation[]>(_loadLS<Conversation[]>(LS_CONVERSATIONS, []))
  const folders = ref<Folder[]>(_loadLS<Folder[]>(LS_FOLDERS, []))
  const activeId = ref<string | null>(_loadLS<string | null>(LS_ACTIVE, null))

  // Si no hay conversaciones al montar, crear una vacía automáticamente
  if (conversations.value.length === 0) {
    const first = _makeConversation(null)
    conversations.value.push(first)
    activeId.value = first.id
  } else if (!activeId.value || !conversations.value.find(c => c.id === activeId.value)) {
    // Si el activeId no existe, apuntar a la primera
    activeId.value = conversations.value[0]!.id
  }

  // ── Persistencia ──────────────────────────────────────────

  watchEffect(() => {
    const toSave = conversations.value.map(c => ({
      ...c,
      messages: c.messages.slice(-100),
    }))
    localStorage.setItem(LS_CONVERSATIONS, JSON.stringify(toSave))
  })

  watchEffect(() => {
    localStorage.setItem(LS_FOLDERS, JSON.stringify(folders.value))
  })

  watchEffect(() => {
    localStorage.setItem(LS_ACTIVE, JSON.stringify(activeId.value))
  })

  // ── Getters ───────────────────────────────────────────────

  const activeConversation = computed<Conversation | null>(
    () => conversations.value.find(c => c.id === activeId.value) ?? null
  )

  const conversationsByFolder = computed<Record<string, Conversation[]>>(() => {
    const result: Record<string, Conversation[]> = { __none__: [] }

    for (const folder of folders.value) {
      result[folder.id] = []
    }

    for (const conv of conversations.value) {
      const key = conv.folderId ?? '__none__'
      if (!result[key]) result[key] = []
      result[key].push(conv)
    }

    // Ordenar cada grupo: pinned primero, luego updatedAt desc
    for (const key of Object.keys(result)) {
      result[key]!.sort((a, b) => {
        if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
        return b.updatedAt - a.updatedAt
      })
    }

    return result
  })

  // ── Helpers privados ──────────────────────────────────────

  function _makeConversation(folderId: string | null): Conversation {
    const now = Date.now()
    return {
      id: crypto.randomUUID(),
      title: 'Nueva conversación',
      sessionId: crypto.randomUUID(),
      folderId,
      createdAt: now,
      updatedAt: now,
      messages: [],
      pinned: false,
    }
  }

  // ── Acciones ──────────────────────────────────────────────

  function createConversation(folderId: string | null = null): Conversation {
    const conv = _makeConversation(folderId)
    conversations.value.unshift(conv)
    activeId.value = conv.id
    return conv
  }

  function setActive(id: string): void {
    activeId.value = id
  }

  function updateTitle(id: string, title: string): void {
    const conv = conversations.value.find(c => c.id === id)
    if (conv) {
      conv.title = title.trim() || 'Nueva conversación'
      conv.updatedAt = Date.now()
    }
  }

  function autoTitle(id: string): void {
    const conv = conversations.value.find(c => c.id === id)
    if (!conv) return
    const firstUserMsg = conv.messages.find(m => m.role === 'user')
    if (!firstUserMsg) return
    conv.title = firstUserMsg.content.slice(0, 45) + (firstUserMsg.content.length > 45 ? '…' : '')
    conv.updatedAt = Date.now()
  }

  function addMessage(id: string, msg: ChatMessage): void {
    const conv = conversations.value.find(c => c.id === id)
    if (!conv) return
    conv.messages.push(msg)
    conv.updatedAt = Date.now()
    if (conv.messages.length === 1) {
      autoTitle(id)
    }
  }

  function updateLastAssistantMessage(id: string, content: string, sources?: SourceInfo[]): void {
    const conv = conversations.value.find(c => c.id === id)
    if (!conv) return
    for (let i = conv.messages.length - 1; i >= 0; i--) {
      const msg = conv.messages[i]!
      if (msg.role === 'assistant') {
        msg.content = content
        if (sources !== undefined) msg.sources = sources
        conv.updatedAt = Date.now()
        break
      }
    }
  }

  function deleteMessage(convId: string, msgId: string): void {
    const conv = conversations.value.find(c => c.id === convId)
    if (!conv) return
    conv.messages = conv.messages.filter(m => m.id !== msgId)
    conv.updatedAt = Date.now()
  }

  function deleteMessagesFrom(convId: string, msgId: string): void {
    const conv = conversations.value.find(c => c.id === convId)
    if (!conv) return
    const idx = conv.messages.findIndex(m => m.id === msgId)
    if (idx !== -1) {
      conv.messages = conv.messages.slice(0, idx)
      conv.updatedAt = Date.now()
    }
  }

  function deleteConversation(id: string): void {
    const idx = conversations.value.findIndex(c => c.id === id)
    if (idx === -1) return
    conversations.value.splice(idx, 1)
    if (activeId.value === id) {
      if (conversations.value.length === 0) {
        const fresh = _makeConversation(null)
        conversations.value.push(fresh)
        activeId.value = fresh.id
      } else {
        activeId.value = conversations.value[0]!.id
      }
    }
  }

  function togglePin(id: string): void {
    const conv = conversations.value.find(c => c.id === id)
    if (conv) conv.pinned = !conv.pinned
  }

  function createFolder(name: string, color: string): Folder {
    const folder: Folder = {
      id: crypto.randomUUID(),
      name: name.trim() || 'Carpeta',
      color,
      collapsed: false,
    }
    folders.value.push(folder)
    return folder
  }

  function renameFolder(id: string, name: string): void {
    const folder = folders.value.find(f => f.id === id)
    if (folder) folder.name = name.trim() || 'Carpeta'
  }

  function deleteFolder(id: string): void {
    folders.value = folders.value.filter(f => f.id !== id)
    // Desvincular conversaciones
    for (const conv of conversations.value) {
      if (conv.folderId === id) conv.folderId = null
    }
  }

  function moveToFolder(conversationId: string, folderId: string | null): void {
    const conv = conversations.value.find(c => c.id === conversationId)
    if (conv) conv.folderId = folderId
  }

  function toggleFolderCollapsed(id: string): void {
    const folder = folders.value.find(f => f.id === id)
    if (folder) folder.collapsed = !folder.collapsed
  }

  return {
    // estado
    conversations,
    folders,
    activeId,
    // getters
    activeConversation,
    conversationsByFolder,
    // acciones
    createConversation,
    setActive,
    updateTitle,
    autoTitle,
    addMessage,
    updateLastAssistantMessage,
    deleteMessage,
    deleteMessagesFrom,
    deleteConversation,
    togglePin,
    createFolder,
    renameFolder,
    deleteFolder,
    moveToFolder,
    toggleFolderCollapsed,
  }
})
