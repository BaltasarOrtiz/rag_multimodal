<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Select from 'primevue/select'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Badge from 'primevue/badge'
import { useCollectionStore } from '@/stores/useCollectionStore'

const store = useCollectionStore()
const toast = useToast()
const confirm = useConfirm()

// ── Create collection dialog ──
const showCreate = ref(false)
const newName = ref('')
const newDescription = ref('')
const nameError = ref('')
const creating = ref(false)

const NAME_RE = /^[a-z0-9][a-z0-9_-]*$/

function validateName(v: string) {
  if (!v) return 'Name is required.'
  if (v.length < 2) return 'Minimum 2 characters.'
  if (v.length > 64) return 'Maximum 64 characters.'
  if (!NAME_RE.test(v)) return 'Lowercase letters, numbers, _ and - only'
  return ''
}

function openCreate() {
  newName.value = ''
  newDescription.value = ''
  nameError.value = ''
  showCreate.value = true
}

async function submitCreate() {
  nameError.value = validateName(newName.value)
  if (nameError.value) return
  creating.value = true
  try {
    await store.createCollection(newName.value.trim(), newDescription.value.trim())
    toast.add({ severity: 'success', summary: 'Collection created', detail: `'${newName.value}' ready to use.`, life: 4000 })
    showCreate.value = false
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: store.error ?? 'Failed to create', life: 5000 })
  } finally {
    creating.value = false
  }
}

// ── Delete collection ──
function confirmDelete(name: string, isDefault: boolean) {
  if (isDefault) {
    toast.add({ severity: 'warn', summary: 'Warning', detail: 'The default collection cannot be deleted.', life: 4000 })
    return
  }
  confirm.require({
    message: `Delete collection '${name}'? All its documents and vectors will be removed. This action cannot be undone.`,
    header: 'Delete collection',
    icon: 'pi pi-exclamation-triangle',
    rejectLabel: 'Cancel',
    acceptLabel: 'Delete',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await store.deleteCollection(name)
        toast.add({ severity: 'warn', summary: 'Deleted', detail: `Collection '${name}' deleted.`, life: 4000 })
      } catch {
        toast.add({ severity: 'error', summary: 'Error', detail: store.error ?? 'Failed to delete', life: 5000 })
      }
    },
  })
}

onMounted(() => store.fetchCollections())
</script>

<template>
  <div class="flex flex-col gap-3.5">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <span class="text-[0.7rem] font-semibold text-cape-cod-500 uppercase tracking-widest">Collections</span>
      <Button
        icon="pi pi-plus"
        size="small"
        text
        rounded
        v-tooltip.left="'New collection'"
        @click="openCreate"
        class="!text-cape-cod-400 hover:!bg-white/10"
      />
    </div>

    <!-- Active collection selector -->
    <div>
      <label class="block text-xs text-cape-cod-400 mb-1.5 font-medium">Active collection</label>
      <Select
        :options="store.collections"
        optionLabel="name"
        optionValue="name"
        v-model="store.activeCollection"
        placeholder="Select collection…"
        class="w-full !bg-white/5 !border-white/10 hover:!border-cape-cod-500/50"
        :loading="store.loading"
      >
        <template #option="{ option }">
          <div class="flex flex-col gap-1 py-0.5">
            <div class="flex items-center gap-1.5 text-[0.875rem] font-medium text-cape-cod-50">
              <span>{{ option.name }}</span>
              <span v-if="option.is_default" class="text-[0.65rem] px-1.5 py-0.5 rounded bg-cape-cod-400/10 text-cape-cod-400 font-semibold tracking-wide">default</span>
            </div>
            <div class="flex gap-3 text-[0.7rem] text-cape-cod-500">
              <span><i class="pi pi-file-o mr-1 text-[0.65rem]" /> {{ option.doc_count }}</span>
              <span><i class="pi pi-server mr-1 text-[0.65rem] text-cape-cod-300" /> {{ option.vector_count.toLocaleString() }}</span>
            </div>
          </div>
        </template>
        <template #value="{ value }">
          <span v-if="value" class="text-cape-cod-50 font-medium">
            <i class="pi pi-database mr-1.5 opacity-60 text-cape-cod-400" />
            {{ value }}
          </span>
          <span v-else class="text-cape-cod-500">Select…</span>
        </template>
      </Select>
    </div>

    <!-- Collections list -->
    <div class="flex flex-col gap-1.5 max-h-60 overflow-y-auto pr-0.5" v-if="store.collections.length">
      <div
        v-for="col in store.collections"
        :key="col.name"
        class="group flex items-center justify-between py-2.5 px-3 rounded-lg border border-white/10 bg-white/5 cursor-pointer transition-all duration-150 gap-2 hover:bg-white/10 hover:border-cape-cod-400/30"
        :class="{ '!border-cape-cod-400/50 bg-cape-cod-400/10': col.name === store.activeCollection }"
        @click="store.setActive(col.name)"
      >
        <div class="flex-1 min-w-0 flex flex-col gap-1">
          <div class="flex items-center gap-1.5 text-[0.8125rem] font-medium text-cape-cod-50">
            <i class="pi pi-database text-[0.7rem] shrink-0 transition-colors duration-150" :class="col.name === store.activeCollection ? 'text-cape-cod-400' : 'text-cape-cod-500'" />
            <span class="overflow-hidden text-ellipsis whitespace-nowrap" :title="col.name">{{ col.name }}</span>
            <Badge v-if="col.is_default" value="default" severity="secondary" class="!text-[0.6rem]" />
          </div>
          <div class="text-[0.7rem] text-cape-cod-500 overflow-hidden text-ellipsis whitespace-nowrap" v-if="col.description">{{ col.description }}</div>
          <div class="flex gap-2 mt-0.5">
            <span class="text-[0.68rem] text-cape-cod-400 flex items-center gap-1" v-tooltip.bottom="'Documents'">
              <i class="pi pi-file-o text-[0.6rem]" /> {{ col.doc_count }}
            </span>
            <span class="text-[0.68rem] text-cape-cod-300 flex items-center gap-1" v-tooltip.bottom="'Indexed vectors'">
              <i class="pi pi-server text-[0.6rem]" /> {{ col.vector_count.toLocaleString() }}
            </span>
          </div>
        </div>
        <Button
          icon="pi pi-trash"
          text
          rounded
          severity="danger"
          size="small"
          v-tooltip.left="col.is_default ? 'The default collection cannot be deleted' : 'Delete collection'"
          :disabled="col.is_default"
          @click.stop="confirmDelete(col.name, col.is_default)"
          class="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
        />
      </div>
    </div>

    <div v-else-if="!store.loading" class="flex flex-col items-center gap-1.5 p-4 text-cape-cod-500 text-sm">
      <i class="pi pi-inbox text-2xl opacity-40" />
      <span>No collections. Create one.</span>
    </div>

    <!-- Refresh button -->
    <Button
      label="Refresh"
      icon="pi pi-refresh"
      text
      size="small"
      :loading="store.loading"
      @click="store.fetchCollections()"
      class="self-end text-xs !text-cape-cod-400 hover:!bg-white/10"
    />
  </div>

  <!-- Create collection dialog -->
  <Dialog
    v-model:visible="showCreate"
    header="New collection"
    modal
    :style="{ width: '28rem' }"
    :closable="!creating"
    class="!bg-cape-cod-900 border-white/10"
  >
    <div class="flex flex-col gap-5 py-2">
      <div class="flex flex-col gap-1.5">
        <label class="text-[0.8125rem] font-medium text-cape-cod-400">Name <span class="text-red-400 ml-0.5">*</span></label>
        <InputText
          v-model="newName"
          placeholder="ej: medicina_2024"
          class="w-full !bg-white/5 !border-white/10"
          :invalid="!!nameError"
          @input="nameError = ''"
          @keyup.enter="submitCreate"
          autofocus
        />
        <small v-if="nameError" class="text-[0.7rem] text-red-400">{{ nameError }}</small>
        <small v-else class="text-[0.7rem] text-cape-cod-500">Lowercase letters, numbers, _ and - only</small>
      </div>

      <div class="flex flex-col gap-1.5">
        <label class="text-[0.8125rem] font-medium text-cape-cod-400">Description <span class="text-[0.7rem] text-cape-cod-500 font-normal ml-1">(optional)</span></label>
        <Textarea
          v-model="newDescription"
          placeholder="Describe the content of this knowledge base…"
          rows="3"
          class="w-full !bg-white/5 !border-white/10 resize-none"
        />
      </div>
    </div>

    <template #footer>
      <Button label="Cancel" text severity="secondary" @click="showCreate = false" :disabled="creating" class="hover:bg-white/10" />
      <Button label="Create collection" icon="pi pi-plus" :loading="creating" @click="submitCreate" class="bg-gradient-to-br from-cape-cod-600 to-cape-cod-800 border-none" />
    </template>
  </Dialog>
</template>

