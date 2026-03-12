<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import { useConversationStore, FOLDER_COLORS } from '@/stores/useConversationStore'

const store = useConversationStore()

// ── Colapso del sidebar ───────────────────────────────────────
const collapsed = defineModel<boolean>('collapsed', { default: false })

// ── Crear carpeta inline ──────────────────────────────────────
const showFolderInput = ref(false)
const newFolderName = ref('')
const newFolderColor = ref<string>(FOLDER_COLORS[0] ?? '#22d3ee')

function confirmCreateFolder() {
  if (newFolderName.value.trim()) {
    store.createFolder(newFolderName.value.trim(), newFolderColor.value)
  }
  newFolderName.value = ''
  newFolderColor.value = FOLDER_COLORS[0] ?? '#22d3ee'
  showFolderInput.value = false
}

// ── Menú contextual de conversación ──────────────────────────
const contextMenu = ref<InstanceType<typeof Popover> | null>(null)
const contextTarget = ref<HTMLElement | null>(null)
const contextConvId = ref<string | null>(null)

function openContextMenu(event: MouseEvent, convId: string) {
  event.stopPropagation()
  contextConvId.value = convId
  contextTarget.value = event.currentTarget as HTMLElement
  nextTick(() => {
    contextMenu.value?.show(event, contextTarget.value)
  })
}

// ── Renombrar inline ──────────────────────────────────────────
const renamingId = ref<string | null>(null)
const renameValue = ref('')

function startRename(convId: string, currentTitle: string) {
  contextMenu.value?.hide()
  renamingId.value = convId
  renameValue.value = currentTitle
  nextTick(() => {
    const input = document.getElementById(`rename-input-${convId}`)
    input?.focus()
  })
}

function confirmRename(convId: string) {
  if (renameValue.value.trim()) {
    store.updateTitle(convId, renameValue.value)
  }
  renamingId.value = null
}

// ── Mover a carpeta (submenu) ─────────────────────────────────
const moveMenu = ref<InstanceType<typeof Popover> | null>(null)

function openMoveMenu(event: MouseEvent) {
  event.stopPropagation()
  moveMenu.value?.show(event, event.currentTarget as HTMLElement)
}

function moveConv(folderId: string | null) {
  if (contextConvId.value) {
    store.moveToFolder(contextConvId.value, folderId)
  }
  contextMenu.value?.hide()
  moveMenu.value?.hide()
}

// ── Carpetas: menú contextual ─────────────────────────────────
const folderMenu = ref<InstanceType<typeof Popover> | null>(null)
const folderMenuId = ref<string | null>(null)
const renamingFolderId = ref<string | null>(null)
const renameFolderValue = ref('')

function openFolderMenu(event: MouseEvent, folderId: string) {
  event.stopPropagation()
  folderMenuId.value = folderId
  folderMenu.value?.show(event, event.currentTarget as HTMLElement)
}

function startRenameFolder(folderId: string, currentName: string) {
  folderMenu.value?.hide()
  renamingFolderId.value = folderId
  renameFolderValue.value = currentName
}

function confirmRenameFolder(folderId: string) {
  if (renameFolderValue.value.trim()) {
    store.renameFolder(folderId, renameFolderValue.value)
  }
  renamingFolderId.value = null
}

function handleDeleteConv(convId: string) {
  if (confirm('¿Eliminar esta conversación?')) {
    store.deleteConversation(convId)
  }
  contextMenu.value?.hide()
}

function handleDeleteFolder(folderId: string) {
  if (confirm('¿Eliminar carpeta? Las conversaciones quedarán sin carpeta.')) {
    store.deleteFolder(folderId)
  }
  folderMenu.value?.hide()
}

// ── Lista de conversaciones sin carpeta ──────────────────────
const noneConversations = computed(() => store.conversationsByFolder['__none__'] ?? [])

// ── Truncar título ────────────────────────────────────────────
function truncate(text: string, max = 28): string {
  return text.length > max ? text.slice(0, max) + '…' : text
}
</script>

<template>
  <aside class="conv-sidebar" :class="{ 'conv-sidebar--collapsed': collapsed }">
    <!-- Toggle button siempre visible -->
    <button class="sidebar-toggle" :title="collapsed ? 'Expandir' : 'Colapsar'" @click="collapsed = !collapsed">
      <i :class="collapsed ? 'pi pi-chevron-right' : 'pi pi-chevron-left'" />
    </button>

    <!-- Contenido (oculto cuando collapsed) -->
    <div class="sidebar-content">
      <!-- Header -->
      <div class="sidebar-header">
        <span class="sidebar-title">CONVERSACIONES</span>
        <div class="header-actions">
          <Button
            icon="pi pi-plus"
            text
            rounded
            size="small"
            class="icon-btn"
            title="Nueva conversación"
            @click="store.createConversation()"
          />
          <Button
            icon="pi pi-folder-plus"
            text
            rounded
            size="small"
            class="icon-btn"
            title="Nueva carpeta"
            @click="showFolderInput = !showFolderInput"
          />
        </div>
      </div>

      <!-- Crear carpeta inline -->
      <Transition name="slide-down">
        <div v-if="showFolderInput" class="folder-create-form">
          <div class="color-picker">
            <button
              v-for="color in FOLDER_COLORS"
              :key="color"
              class="color-dot"
              :class="{ active: newFolderColor === color }"
              :style="{ background: color }"
              @click="newFolderColor = color"
            />
          </div>
          <div class="folder-name-row">
            <input
              v-model="newFolderName"
              class="inline-input"
              placeholder="Nombre de carpeta"
              @keydown.enter="confirmCreateFolder"
              @keydown.esc="showFolderInput = false"
            />
            <Button icon="pi pi-check" text rounded size="small" class="icon-btn confirm-btn" @click="confirmCreateFolder" />
          </div>
        </div>
      </Transition>

      <!-- Lista de conversaciones y carpetas -->
      <div class="conv-list">

        <!-- Conversaciones sin carpeta -->
        <template v-for="conv in noneConversations" :key="conv.id">
          <div
            class="conv-item"
            :class="{ active: store.activeId === conv.id }"
            @click="store.setActive(conv.id)"
          >
            <template v-if="renamingId === conv.id">
              <input
                :id="`rename-input-${conv.id}`"
                v-model="renameValue"
                class="inline-input rename-input"
                @blur="confirmRename(conv.id)"
                @keydown.enter="confirmRename(conv.id)"
                @keydown.esc="renamingId = null"
                @click.stop
              />
            </template>
            <template v-else>
              <i class="pi pi-comments conv-icon" />
              <span class="conv-title-text">{{ truncate(conv.title) }}</span>
              <i v-if="conv.pinned" class="pi pi-bookmark pin-icon" />
              <button class="context-btn" @click.stop="openContextMenu($event, conv.id)">
                <i class="pi pi-ellipsis-v" />
              </button>
            </template>
          </div>
        </template>

        <!-- Carpetas -->
        <template v-for="folder in store.folders" :key="folder.id">
          <!-- Header de carpeta -->
          <div class="folder-header" @click="store.toggleFolderCollapsed(folder.id)">
            <i class="pi pi-folder folder-icon" :style="{ color: folder.color }" />
            <template v-if="renamingFolderId === folder.id">
              <input
                v-model="renameFolderValue"
                class="inline-input rename-input"
                @blur="confirmRenameFolder(folder.id)"
                @keydown.enter="confirmRenameFolder(folder.id)"
                @keydown.esc="renamingFolderId = null"
                @click.stop
              />
            </template>
            <template v-else>
              <span class="folder-name">{{ truncate(folder.name, 22) }}</span>
            </template>
            <i
              class="pi folder-chevron"
              :class="folder.collapsed ? 'pi-chevron-right' : 'pi-chevron-down'"
            />
            <button class="context-btn" @click.stop="openFolderMenu($event, folder.id)">
              <i class="pi pi-ellipsis-v" />
            </button>
          </div>

          <!-- Conversaciones de la carpeta -->
          <Transition name="folder-expand">
            <div v-show="!folder.collapsed" class="folder-conversations">
              <div
                v-for="conv in (store.conversationsByFolder[folder.id] ?? [])"
                :key="conv.id"
                class="conv-item conv-item--indented"
                :class="{ active: store.activeId === conv.id }"
                @click="store.setActive(conv.id)"
              >
                <template v-if="renamingId === conv.id">
                  <input
                    :id="`rename-input-${conv.id}`"
                    v-model="renameValue"
                    class="inline-input rename-input"
                    @blur="confirmRename(conv.id)"
                    @keydown.enter="confirmRename(conv.id)"
                    @keydown.esc="renamingId = null"
                    @click.stop
                  />
                </template>
                <template v-else>
                  <i class="pi pi-comments conv-icon" />
                  <span class="conv-title-text">{{ truncate(conv.title) }}</span>
                  <i v-if="conv.pinned" class="pi pi-bookmark pin-icon" />
                  <button class="context-btn" @click.stop="openContextMenu($event, conv.id)">
                    <i class="pi pi-ellipsis-v" />
                  </button>
                </template>
              </div>
            </div>
          </Transition>
        </template>

      </div>
    </div>

    <!-- Popover menú contextual de conversación -->
    <Popover ref="contextMenu" class="conv-popover">
      <div class="popover-menu">
        <button class="popover-item" @click="contextConvId && startRename(contextConvId, store.conversations.find(c => c.id === contextConvId)?.title ?? '')">
          <i class="pi pi-pencil" /> Renombrar
        </button>
        <button class="popover-item" @click="contextConvId && store.togglePin(contextConvId); contextMenu?.hide()">
          <i class="pi pi-bookmark" />
          {{ contextConvId && store.conversations.find(c => c.id === contextConvId)?.pinned ? 'Quitar pin' : 'Pinear' }}
        </button>
        <button class="popover-item" @click="openMoveMenu($event)">
          <i class="pi pi-folder" /> Mover a carpeta <i class="pi pi-chevron-right" style="margin-left:auto;font-size:0.7rem" />
        </button>
        <div class="popover-divider" />
        <button class="popover-item popover-item--danger" @click="contextConvId && handleDeleteConv(contextConvId)">
          <i class="pi pi-trash" /> Eliminar
        </button>
      </div>
    </Popover>

    <!-- Submenu: mover a carpeta -->
    <Popover ref="moveMenu" class="conv-popover">
      <div class="popover-menu">
        <button class="popover-item" @click="moveConv(null)">
          <i class="pi pi-inbox" /> Sin carpeta
        </button>
        <button
          v-for="folder in store.folders"
          :key="folder.id"
          class="popover-item"
          @click="moveConv(folder.id)"
        >
          <i class="pi pi-folder" :style="{ color: folder.color }" /> {{ truncate(folder.name, 20) }}
        </button>
      </div>
    </Popover>

    <!-- Popover menú de carpeta -->
    <Popover ref="folderMenu" class="conv-popover">
      <div class="popover-menu">
        <button class="popover-item" @click="folderMenuId && startRenameFolder(folderMenuId, store.folders.find(f => f.id === folderMenuId)?.name ?? '')">
          <i class="pi pi-pencil" /> Renombrar
        </button>
        <div class="popover-divider" />
        <button class="popover-item popover-item--danger" @click="folderMenuId && handleDeleteFolder(folderMenuId)">
          <i class="pi pi-trash" /> Eliminar carpeta
        </button>
      </div>
    </Popover>
  </aside>
</template>

<style scoped>
.conv-sidebar {
  width: 260px;
  min-width: 260px;
  background: rgba(10, 10, 15, 0.6);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.25s ease, min-width 0.25s ease;
  flex-shrink: 0;
}

.conv-sidebar--collapsed {
  width: 40px;
  min-width: 40px;
  overflow: hidden;
}

.conv-sidebar--collapsed .sidebar-content {
  opacity: 0;
  pointer-events: none;
}

.sidebar-toggle {
  position: absolute;
  top: 12px;
  right: -14px;
  z-index: 10;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.625rem;
  transition: color 0.2s, border-color 0.2s;
}

.sidebar-toggle:hover {
  color: var(--cyan-400);
  border-color: rgba(34, 211, 238, 0.4);
}

.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: opacity 0.2s;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 0.75rem 0.5rem;
  flex-shrink: 0;
}

.sidebar-title {
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.header-actions {
  display: flex;
  gap: 0.125rem;
}

.icon-btn {
  color: var(--text-muted) !important;
  width: 1.75rem !important;
  height: 1.75rem !important;
  padding: 0 !important;
}

.icon-btn:hover {
  color: var(--cyan-400) !important;
}

/* Crear carpeta */
.folder-create-form {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.color-picker {
  display: flex;
  gap: 0.375rem;
  flex-wrap: wrap;
}

.color-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
  padding: 0;
  transition: transform 0.15s;
}

.color-dot.active {
  border-color: #fff;
  transform: scale(1.2);
}

.folder-name-row {
  display: flex;
  gap: 0.25rem;
  align-items: center;
}

.inline-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 0.8125rem;
  padding: 0.25rem 0.5rem;
  outline: none;
}

.inline-input:focus {
  border-color: rgba(34, 211, 238, 0.4);
}

.confirm-btn {
  color: #4ade80 !important;
}

/* Lista de conversaciones */
.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.25rem 0;
  scrollbar-width: thin;
  scrollbar-color: var(--border-subtle) transparent;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  border-radius: 0;
  border-left: 2px solid transparent;
  transition: background 0.15s, border-color 0.15s;
  min-height: 36px;
}

.conv-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.conv-item.active {
  background: rgba(34, 211, 238, 0.08);
  border-left-color: var(--cyan-400);
}

.conv-item--indented {
  padding-left: 1.5rem;
}

.conv-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
  flex-shrink: 0;
}

.conv-title-text {
  flex: 1;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.conv-item.active .conv-title-text {
  color: var(--cyan-400);
}

.pin-icon {
  font-size: 0.625rem;
  color: #facc15;
  flex-shrink: 0;
}

.context-btn {
  display: none;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.125rem 0.25rem;
  border-radius: 4px;
  font-size: 0.75rem;
  flex-shrink: 0;
}

.conv-item:hover .context-btn {
  display: flex;
  align-items: center;
}

.context-btn:hover {
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.06);
}

.rename-input {
  flex: 1;
  min-width: 0;
}

/* Carpetas */
.folder-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  transition: background 0.15s;
}

.folder-header:hover {
  background: rgba(255, 255, 255, 0.04);
}

.folder-icon {
  font-size: 0.875rem;
  flex-shrink: 0;
}

.folder-name {
  flex: 1;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.folder-chevron {
  font-size: 0.625rem;
  color: var(--text-muted);
  flex-shrink: 0;
}

.folder-header .context-btn {
  display: none;
}

.folder-header:hover .context-btn {
  display: flex;
  align-items: center;
}

.folder-conversations { display: block; }

/* Popover */
:deep(.conv-popover .p-popover-content) {
  padding: 0.25rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  min-width: 160px;
}

.popover-menu {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.popover-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 0.8125rem;
  cursor: pointer;
  border-radius: 6px;
  width: 100%;
  text-align: left;
  transition: background 0.15s, color 0.15s;
}

.popover-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary);
}

.popover-item--danger {
  color: #f87171;
}

.popover-item--danger:hover {
  background: rgba(248, 113, 113, 0.08);
}

.popover-divider {
  height: 1px;
  background: var(--border-subtle);
  margin: 0.125rem 0.5rem;
}

/* Transitions */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
}
.slide-down-enter-to,
.slide-down-leave-from {
  opacity: 1;
  max-height: 120px;
}

.folder-expand-enter-active,
.folder-expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.folder-expand-enter-from,
.folder-expand-leave-to {
  opacity: 0;
}

/* Mobile */
@media (max-width: 767px) {
  .conv-sidebar {
    position: fixed;
    top: 64px;
    left: 0;
    bottom: 0;
    z-index: 200;
    width: 260px !important;
    min-width: 260px !important;
    transform: translateX(0);
    transition: transform 0.25s ease;
  }

  .conv-sidebar--collapsed {
    transform: translateX(-260px);
    width: 260px !important;
    min-width: 260px !important;
  }

  .sidebar-toggle {
    right: -40px;
    top: 50%;
    transform: translateY(-50%);
  }
}
</style>
