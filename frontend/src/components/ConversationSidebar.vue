<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import { useConversationStore, FOLDER_COLORS } from '@/stores/useConversationStore'

const store = useConversationStore()

// ── Sidebar collapse ───────────────────────────────────────
const collapsed = defineModel<boolean>('collapsed', { default: false })

// ── Create folder inline ──────────────────────────────────────
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

// ── Conversation context menu ──────────────────────────────────────
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

// ── Inline rename ──────────────────────────────────────────
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

// ── Move to folder (submenu) ─────────────────────────────────
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

// ── Folders: context menu ─────────────────────────────────
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
  if (confirm('Delete this conversation?')) {
    store.deleteConversation(convId)
  }
  contextMenu.value?.hide()
}

function handleDeleteFolder(folderId: string) {
  if (confirm('Delete folder? Conversations will become unfoldered.')) {
    store.deleteFolder(folderId)
  }
  folderMenu.value?.hide()
}

// ── List of conversations without a folder ──────────────────────
const noneConversations = computed(() => store.conversationsByFolder['__none__'] ?? [])

// ── Truncate title ────────────────────────────────────────────
function truncate(text: string, max = 28): string {
  return text.length > max ? text.slice(0, max) + '…' : text
}
</script>


<template>
  <aside
    class="bg-[#0f0f0f] border-r border-white/6 flex flex-col transition-all duration-300 ease-in-out shrink-0 z-[200] fixed md:static top-16 md:top-0 bottom-0 left-0"
    :class="collapsed
      ? 'w-[84vw] max-w-[300px] -translate-x-full md:translate-x-0 md:w-[260px] md:min-w-[260px]'
      : 'w-[84vw] max-w-[300px] translate-x-0 md:w-[260px] md:min-w-[260px]'"
  >
    <!-- Toggle button on mobile -->
    <button 
      class="md:hidden absolute top-3 -right-3.5 z-10 w-7 h-7 rounded-full bg-[#0f0f0f] border border-white/10 text-zinc-500 cursor-pointer flex items-center justify-center text-[0.625rem] transition-colors hover:text-zinc-300 hover:border-white/20" 
      :title="collapsed ? 'Expand' : 'Collapse'" 
      @click="collapsed = !collapsed"
    >
      <i :class="collapsed ? 'pi pi-chevron-right' : 'pi pi-chevron-left'" />
    </button>

    <!-- Content (hidden when collapsed) -->
    <div class="flex-1 flex flex-col overflow-hidden transition-opacity duration-200" :class="{ 'opacity-0 pointer-events-none': collapsed }">
      <div class="p-3.5">
        <button
          class="w-full flex items-center justify-between px-3.5 py-2.5 bg-zinc-900 border border-white/10 rounded-xl hover:bg-zinc-800 transition-colors"
          @click="store.createConversation()"
        >
          <span class="text-sm font-medium text-zinc-300">New conversation</span>
          <i class="pi pi-plus text-xs text-zinc-500" />
        </button>
      </div>

      <!-- Header -->
      <div class="flex items-center justify-between px-3 pt-1 pb-2 shrink-0">
        <span class="text-[0.6rem] font-bold tracking-[0.16em] text-zinc-600 uppercase">Conversations</span>
        <div class="flex gap-0.5">
          <Button
            icon="pi pi-folder-plus"
            text
            rounded
            size="small"
            class="!text-zinc-500 !w-7 !h-7 !p-0 hover:!text-zinc-300"
            title="New folder"
            @click="showFolderInput = !showFolderInput"
          />
        </div>
      </div>

      <!-- Create folder inline -->
      <Transition name="slide-down">
        <div v-if="showFolderInput" class="px-3 py-2 border-b border-white/8 flex flex-col gap-2">
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
              class="flex-1 bg-white/5 border border-white/10 rounded-md text-zinc-200 text-[0.8125rem] px-2 py-1 outline-none focus:border-zinc-500"
              placeholder="Folder name"
              @keydown.enter="confirmCreateFolder"
              @keydown.esc="showFolderInput = false"
            />
            <Button icon="pi pi-check" text rounded size="small" class="!text-emerald-400 !w-7 !h-7 !p-0" @click="confirmCreateFolder" />
          </div>
        </div>
      </Transition>

      <!-- Conversations and folders list -->
      <div class="flex-1 overflow-y-auto py-1 custom-scrollbar px-1.5">

        <!-- Conversations without folder -->
        <template v-for="conv in noneConversations" :key="conv.id">
          <div
            class="flex items-center gap-2 px-2.5 py-2 cursor-pointer rounded-lg transition-colors min-h-[36px] group"
            :class="[
              store.activeId === conv.id
                ? 'bg-white/6 border-l-2 border-l-blue-500'
                : 'hover:bg-white/5'
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
              <i class="pi pi-comments text-[0.72rem] text-zinc-600 shrink-0" />
              <span class="flex-1 text-[0.8125rem] whitespace-nowrap overflow-hidden text-ellipsis min-w-0" :class="store.activeId === conv.id ? 'text-zinc-200' : 'text-zinc-500'">{{ truncate(conv.title) }}</span>
              <i v-if="conv.pinned" class="pi pi-bookmark text-[0.625rem] text-yellow-500 shrink-0" />
              <button class="hidden group-hover:flex items-center justify-center p-1 rounded bg-transparent border-none text-zinc-600 hover:text-zinc-300 hover:bg-white/5 shrink-0 text-[0.75rem]" @click.stop="openContextMenu($event, conv.id)">
                <i class="pi pi-ellipsis-v" />
              </button>
            </template>
          </div>
        </template>

        <!-- Folders -->
        <template v-for="folder in store.folders" :key="folder.id">
          <!-- Folder header -->
          <div class="flex items-center gap-2 px-2.5 py-2 cursor-pointer transition-colors hover:bg-white/5 rounded-lg group" @click="store.toggleFolderCollapsed(folder.id)">
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
              <span class="flex-1 text-[0.8125rem] text-zinc-300 font-medium whitespace-nowrap overflow-hidden text-ellipsis min-w-0">{{ truncate(folder.name, 22) }}</span>
            </template>
            <i
              class="pi text-[0.625rem] text-zinc-600 shrink-0"
              :class="folder.collapsed ? 'pi-chevron-right' : 'pi-chevron-down'"
            />
            <button class="hidden group-hover:flex items-center justify-center p-1 rounded bg-transparent border-none text-zinc-600 hover:text-zinc-300 hover:bg-white/5 shrink-0 text-[0.75rem]" @click.stop="openFolderMenu($event, folder.id)">
              <i class="pi pi-ellipsis-v" />
            </button>
          </div>

          <!-- Folder conversations -->
          <Transition name="folder-expand">
            <div v-show="!folder.collapsed" class="block">
              <div
                v-for="conv in (store.conversationsByFolder[folder.id] ?? [])"
                :key="conv.id"
                class="flex items-center gap-2 pl-6 pr-3 py-2 cursor-pointer rounded-lg transition-colors min-h-[36px] group"
                :class="[
                  store.activeId === conv.id
                    ? 'bg-white/6 border-l-2 border-l-blue-500'
                    : 'hover:bg-white/5'
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
                  <i class="pi pi-comments text-[0.75rem] text-zinc-600 shrink-0" />
                  <span class="flex-1 text-[0.8125rem] whitespace-nowrap overflow-hidden text-ellipsis min-w-0" :class="store.activeId === conv.id ? 'text-zinc-200' : 'text-zinc-500'">{{ truncate(conv.title) }}</span>
                  <i v-if="conv.pinned" class="pi pi-bookmark text-[0.625rem] text-yellow-500 shrink-0" />
                  <button class="hidden group-hover:flex items-center justify-center p-1 rounded bg-transparent border-none text-zinc-600 hover:text-zinc-300 hover:bg-white/5 shrink-0 text-[0.75rem]" @click.stop="openContextMenu($event, conv.id)">
                    <i class="pi pi-ellipsis-v" />
                  </button>
                </template>
              </div>
            </div>
          </Transition>
        </template>

      </div>

      <div class="px-3 py-3 border-t border-white/6">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-full bg-zinc-800 border border-white/10 flex items-center justify-center text-[0.65rem] font-bold text-zinc-300">JD</div>
          <div class="min-w-0">
            <p class="m-0 text-[0.8rem] text-zinc-300 leading-tight truncate">John Doe</p>
            <p class="m-0 text-[0.62rem] text-zinc-500 leading-tight uppercase tracking-wide">Pro Plan</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Conversation context menu popover -->
    <Popover ref="contextMenu" class="conv-popover" :pt="{ content: { class: 'p-1 bg-cape-cod-900 border border-white/10 rounded-lg min-w-[160px]' } }">
      <div class="flex flex-col gap-0.5">
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50" @click="contextConvId && startRename(contextConvId, store.conversations.find(c => c.id === contextConvId)?.title ?? '')">
          <i class="pi pi-pencil" /> Rename
        </button>
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50" @click="contextConvId && store.togglePin(contextConvId); contextMenu?.hide()">
          <i class="pi pi-bookmark" />
          {{ contextConvId && store.conversations.find(c => c.id === contextConvId)?.pinned ? 'Unpin' : 'Pin' }}
        </button>
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50" @click="openMoveMenu($event)">
          <i class="pi pi-folder" /> Move to folder <i class="pi pi-chevron-right ml-auto text-[0.7rem]" />
        </button>
        <div class="h-px bg-white/10 my-0.5 mx-2" />
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-red-400 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-red-400/10" @click="contextConvId && handleDeleteConv(contextConvId)">
          <i class="pi pi-trash" /> Delete
        </button>
      </div>
    </Popover>

    <!-- Submenu: move to folder -->
    <Popover ref="moveMenu" class="conv-popover" :pt="{ content: { class: 'p-1 bg-cape-cod-900 border border-white/10 rounded-lg min-w-[160px]' } }">
      <div class="flex flex-col gap-0.5">
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50" @click="moveConv(null)">
          <i class="pi pi-inbox" /> No folder
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

    <!-- Folder menu popover -->
    <Popover ref="folderMenu" class="conv-popover" :pt="{ content: { class: 'p-1 bg-cape-cod-900 border border-white/10 rounded-lg min-w-[160px]' } }">
      <div class="flex flex-col gap-0.5">
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-cape-cod-300 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-white/5 hover:text-cape-cod-50" @click="folderMenuId && startRenameFolder(folderMenuId, store.folders.find(f => f.id === folderMenuId)?.name ?? '')">
          <i class="pi pi-pencil" /> Rename
        </button>
        <div class="h-px bg-white/10 my-0.5 mx-2" />
        <button class="flex items-center gap-2 px-3 py-2 bg-transparent border-none text-red-400 text-[0.8125rem] cursor-pointer rounded-md w-full text-left transition-colors hover:bg-red-400/10" @click="folderMenuId && handleDeleteFolder(folderMenuId)">
          <i class="pi pi-trash" /> Delete folder
        </button>
      </div>
    </Popover>
  </aside>
</template>

<style scoped>
/* Transition animations */
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
