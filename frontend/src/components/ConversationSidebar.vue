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
  <aside 
    class="w-[260px] min-w-[260px] bg-black/40 border-r border-white/5 flex flex-col relative transition-all duration-300 ease-in-out shrink-0 z-[200] md:relative fixed top-16 md:top-0 bottom-0 left-0"
    :class="{ 'w-10 min-w-[40px] md:w-10 md:min-w-[40px] -translate-x-[260px] md:translate-x-0': collapsed }"
  >
    <!-- Toggle button siempre visible -->
    <button 
      class="absolute top-3 -right-3.5 z-10 w-7 h-7 rounded-full bg-cape-cod-900 border border-white/10 text-cape-cod-500 cursor-pointer flex items-center justify-center text-[0.625rem] transition-colors hover:text-cape-cod-300 hover:border-white/20 md:right-[-14px] right-[-40px] md:top-3 top-1/2 md:translate-y-0 -translate-y-1/2" 
      :title="collapsed ? 'Expandir' : 'Colapsar'" 
      @click="collapsed = !collapsed"
    >
      <i :class="collapsed ? 'pi pi-chevron-right' : 'pi pi-chevron-left'" />
    </button>

    <!-- Contenido (oculto cuando collapsed) -->
    <div class="flex-1 flex flex-col overflow-hidden transition-opacity duration-200" :class="{ 'opacity-0 pointer-events-none': collapsed }">
      <!-- Header -->
      <div class="flex items-center justify-between px-3 pt-3 pb-2 shrink-0">
        <span class="text-[0.625rem] font-semibold tracking-widest text-cape-cod-500 uppercase">Conversaciones</span>
        <div class="flex gap-0.5">
          <Button
            icon="pi pi-plus"
            text
            rounded
            size="small"
            class="!text-cape-cod-500 !w-7 !h-7 !p-0 hover:!text-cape-cod-300"
            title="Nueva conversación"
            @click="store.createConversation()"
          />
          <Button
            icon="pi pi-folder-plus"
            text
            rounded
            size="small"
            class="!text-cape-cod-500 !w-7 !h-7 !p-0 hover:!text-cape-cod-300"
            title="Nueva carpeta"
            @click="showFolderInput = !showFolderInput"
          />
        </div>
      </div>

      <!-- Crear carpeta inline -->
      <Transition name="slide-down">
        <div v-if="showFolderInput" class="px-3 py-2 border-b border-white/5 flex flex-col gap-2">
          <div class="flex gap-1.5 flex-wrap">
            <button
              v-for="color in FOLDER_COLORS"
              :key="color"
              class="w-4 h-4 rounded-full cursor-pointer border-2 p-0 transition-transform duration-150"
              :class="{ 'border-white scale-125': newFolderColor === color, 'border-transparent': newFolderColor !== color }"
              :style="{ background: color }"
              @click="newFolderColor = color"
            />
          </div>
          <div class="flex gap-1 items-center">
            <input
              v-model="newFolderName"
              class="flex-1 bg-white/5 border border-white/10 rounded-md text-cape-cod-50 text-[0.8125rem] px-2 py-1 outline-none focus:border-cape-cod-400"
              placeholder="Nombre de carpeta"
              @keydown.enter="confirmCreateFolder"
              @keydown.esc="showFolderInput = false"
            />
            <Button icon="pi pi-check" text rounded size="small" class="!text-green-400 !w-7 !h-7 !p-0" @click="confirmCreateFolder" />
          </div>
        </div>
      </Transition>

      <!-- Lista de conversaciones y carpetas -->
      <div class="flex-1 overflow-y-auto py-1 custom-scrollbar">

        <!-- Conversaciones sin carpeta -->
        <template v-for="conv in noneConversations" :key="conv.id">
          <div
            class="flex items-center gap-2 px-3 py-2 cursor-pointer border-l-2 transition-colors min-h-[36px] group"
            :class="[
              store.activeId === conv.id
                ? 'bg-cape-cod-400/10 border-cape-cod-400'
                : 'border-transparent hover:bg-white/5'
            ]"
            @click="store.setActive(conv.id)"
          >
            <template v-if="renamingId === conv.id">
              <input
                :id="`rename-input-${conv.id}`"
                v-model="renameValue"
                class="flex-1 min-w-0 bg-white/5 border border-cape-cod-400/50 rounded text-cape-cod-50 text-[0.8125rem] px-1.5 py-0.5 outline-none"
                @blur="confirmRename(conv.id)"
                @keydown.enter="confirmRename(conv.id)"
                @keydown.esc="renamingId = null"
                @click.stop
              />
            </template>
            <template v-else>
              <i class="pi pi-comments text-[0.75rem] text-cape-cod-500 shrink-0" />
              <span class="flex-1 text-[0.8125rem] whitespace-nowrap overflow-hidden text-ellipsis min-w-0" :class="store.activeId === conv.id ? 'text-cape-cod-300' : 'text-cape-cod-400'">{{ truncate(conv.title) }}</span>
              <i v-if="conv.pinned" class="pi pi-bookmark text-[0.625rem] text-yellow-500 shrink-0" />
              <button class="hidden group-hover:flex items-center justify-center p-1 rounded bg-transparent border-none text-cape-cod-500 hover:text-cape-cod-300 hover:bg-white/5 shrink-0 text-[0.75rem]" @click.stop="openContextMenu($event, conv.id)">
                <i class="pi pi-ellipsis-v" />
              </button>
            </template>
          </div>
        </template>

        <!-- Carpetas -->
        <template v-for="folder in store.folders" :key="folder.id">
          <!-- Header de carpeta -->
          <div class="flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors hover:bg-white/5 group" @click="store.toggleFolderCollapsed(folder.id)">
            <i class="pi pi-folder text-[0.875rem] shrink-0" :style="{ color: folder.color }" />
            <template v-if="renamingFolderId === folder.id">
              <input
                v-model="renameFolderValue"
                class="flex-1 min-w-0 bg-white/5 border border-cape-cod-400/50 rounded text-cape-cod-50 text-[0.8125rem] px-1.5 py-0.5 outline-none"
                @blur="confirmRenameFolder(folder.id)"
                @keydown.enter="confirmRenameFolder(folder.id)"
                @keydown.esc="renamingFolderId = null"
                @click.stop
              />
            </template>
            <template v-else>
              <span class="flex-1 text-[0.8125rem] text-cape-cod-300 font-medium whitespace-nowrap overflow-hidden text-ellipsis min-w-0">{{ truncate(folder.name, 22) }}</span>
            </template>
            <i
              class="pi text-[0.625rem] text-cape-cod-500 shrink-0"
              :class="folder.collapsed ? 'pi-chevron-right' : 'pi-chevron-down'"
            />
            <button class="hidden group-hover:flex items-center justify-center p-1 rounded bg-transparent border-none text-cape-cod-500 hover:text-cape-cod-300 hover:bg-white/5 shrink-0 text-[0.75rem]" @click.stop="openFolderMenu($event, folder.id)">
              <i class="pi pi-ellipsis-v" />
            </button>
          </div>

          <!-- Conversaciones de la carpeta -->
          <Transition name="folder-expand">
            <div v-show="!folder.collapsed" class="block">
              <div
                v-for="conv in (store.conversationsByFolder[folder.id] ?? [])"
                :key="conv.id"
                class="flex items-center gap-2 pl-6 pr-3 py-2 cursor-pointer border-l-2 transition-colors min-h-[36px] group"
                :class="[
                  store.activeId === conv.id
                    ? 'bg-cape-cod-400/10 border-cape-cod-400'
                    : 'border-transparent hover:bg-white/5'
                ]"
                @click="store.setActive(conv.id)"
              >
                <template v-if="renamingId === conv.id">
                  <input
                    :id="`rename-input-${conv.id}`"
                    v-model="renameValue"
                    class="flex-1 min-w-0 bg-white/5 border border-cape-cod-400/50 rounded text-cape-cod-50 text-[0.8125rem] px-1.5 py-0.5 outline-none"
                    @blur="confirmRename(conv.id)"
                    @keydown.enter="confirmRename(conv.id)"
                    @keydown.esc="renamingId = null"
                    @click.stop
                  />
                </template>
                <template v-else>
                  <i class="pi pi-comments text-[0.75rem] text-cape-cod-500 shrink-0" />
                  <span class="flex-1 text-[0.8125rem] whitespace-nowrap overflow-hidden text-ellipsis min-w-0" :class="store.activeId === conv.id ? 'text-cape-cod-300' : 'text-cape-cod-400'">{{ truncate(conv.title) }}</span>
                  <i v-if="conv.pinned" class="pi pi-bookmark text-[0.625rem] text-yellow-500 shrink-0" />
                  <button class="hidden group-hover:flex items-center justify-center p-1 rounded bg-transparent border-none text-cape-cod-500 hover:text-cape-cod-300 hover:bg-white/5 shrink-0 text-[0.75rem]" @click.stop="openContextMenu($event, conv.id)">
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
    <Popover ref="contextMenu" class="conv-popover" :pt="{ content: { class: 'p-1 bg-cape-cod-900 border border-white/10 rounded-lg min-w-[160px]' } }">
      <div class="flex flex-col gap-0.5">
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50" @click="contextConvId && startRename(contextConvId, store.conversations.find(c => c.id === contextConvId)?.title ?? '')">
          <i class="pi pi-pencil" /> Renombrar
        </button>
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50" @click="contextConvId && store.togglePin(contextConvId); contextMenu?.hide()">
          <i class="pi pi-bookmark" />
          {{ contextConvId && store.conversations.find(c => c.id === contextConvId)?.pinned ? 'Quitar pin' : 'Pinear' }}
        </button>
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50" @click="openMoveMenu($event)">
          <i class="pi pi-folder" /> Mover a carpeta <i class="pi pi-chevron-right ml-auto text-[0.7rem]" />
        </button>
        <div class="h-px bg-white/10 my-0.5 mx-2" />
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-red-400 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-red-400/10" @click="contextConvId && handleDeleteConv(contextConvId)">
          <i class="pi pi-trash" /> Eliminar
        </button>
      </div>
    </Popover>

    <!-- Submenu: mover a carpeta -->
    <Popover ref="moveMenu" class="conv-popover" :pt="{ content: { class: 'p-1 bg-cape-cod-900 border border-white/10 rounded-lg min-w-[160px]' } }">
      <div class="flex flex-col gap-0.5">
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50" @click="moveConv(null)">
          <i class="pi pi-inbox" /> Sin carpeta
        </button>
        <button
          v-for="folder in store.folders"
          :key="folder.id"
          class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50"
          @click="moveConv(folder.id)"
        >
          <i class="pi pi-folder" :style="{ color: folder.color }" /> {{ truncate(folder.name, 20) }}
        </button>
      </div>
    </Popover>

    <!-- Popover menú de carpeta -->
    <Popover ref="folderMenu" class="conv-popover" :pt="{ content: { class: 'p-1 bg-cape-cod-900 border border-white/10 rounded-lg min-w-[160px]' } }">
      <div class="flex flex-col gap-0.5">
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50" @click="folderMenuId && startRenameFolder(folderMenuId, store.folders.find(f => f.id === folderMenuId)?.name ?? '')">
          <i class="pi pi-pencil" /> Renombrar
        </button>
        <div class="h-px bg-white/10 my-0.5 mx-2" />
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-red-400 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-red-400/10" @click="folderMenuId && handleDeleteFolder(folderMenuId)">
          <i class="pi pi-trash" /> Eliminar carpeta
        </button>
      </div>
    </Popover>
  </aside>
</template>

<style scoped>
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

.custom-scrollbar {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}
</style>
