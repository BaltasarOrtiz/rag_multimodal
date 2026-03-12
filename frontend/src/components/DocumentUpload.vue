<script setup lang="ts">
import { ref, watch } from 'vue'
import FileUpload from 'primevue/fileupload'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { useDocuments } from '@/composables/useRag'
import { useCollectionStore } from '@/stores/useCollectionStore'

const toast = useToast()
const { documents, loading, error, fetchDocuments, upload, deleteDocument } = useDocuments()
const collectionStore = useCollectionStore()

// Recargar documentos cuando cambia la colección activa
watch(() => collectionStore.activeCollection, () => fetchDocuments())

const uploading = ref(false)
const deletingDoc = ref<string | null>(null)

async function handleDelete(name: string) {
  deletingDoc.value = name
  try {
    const msg = await deleteDocument(name)
    toast.add({ severity: 'success', summary: 'Eliminado', detail: msg, life: 3000 })
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: error.value ?? 'No se pudo eliminar', life: 5000 })
  } finally {
    deletingDoc.value = null
  }
}

fetchDocuments()

async function onFileSelect(event: any) {
  const files: File[] = event.files
  if (!files.length) return
  uploading.value = true
  try {
    for (const file of files) {
      const msg = await upload(file)
      toast.add({ severity: 'success', summary: 'Subido', detail: msg, life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: error.value ?? 'Fallo al subir', life: 5000 })
  } finally {
    uploading.value = false
  }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <div class="p-5 flex flex-col gap-4 bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl transition-all duration-200 hover:bg-white/10 hover:border-cape-cod-600/30">
    <div class="flex items-center gap-2.5 text-sm font-semibold text-cape-cod-400 uppercase tracking-wide flex-wrap">
      <i class="pi pi-cloud-upload text-cape-cod-400 text-base" />
      <h3>Documentos</h3>
      <span v-if="collectionStore.activeCollection" class="ml-auto inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[0.7rem] font-semibold text-cape-cod-400 bg-cape-cod-400/10 border border-cape-cod-400/25 normal-case tracking-normal">
        <i class="pi pi-th-large text-[0.6rem] text-cape-cod-400" /> {{ collectionStore.activeCollection }}
      </span>
    </div>

    <FileUpload
      mode="advanced"
      multiple
      accept=".pdf,.png,.jpg,.jpeg,.txt,.md"
      :max-file-size="50_000_000"
      :show-upload-button="false"
      :show-cancel-button="false"
      custom-upload
      @select="onFileSelect"
      :pt="{
        root: { class: 'w-full !bg-transparent !border !border-dashed !border-white/10 !rounded-xl transition-colors duration-200 hover:!border-cape-cod-500' },
        buttonbar: { class: '!bg-transparent !border-none !border-b !border-white/10 !px-3.5 !py-2.5' },
        content: { class: '!p-0' },
      }"
    >
      <template #empty>
        <div class="flex flex-col items-center gap-2 p-8 text-cape-cod-500">
          <i class="pi pi-file-arrow-up text-4xl text-cape-cod-500 opacity-60" />
          <p class="text-[0.875rem] font-medium text-cape-cod-400">Arrastrá PDFs, imágenes o texto</p>
          <p class="text-xs text-cape-cod-500">Máx. 50 MB por archivo</p>
        </div>
      </template>
    </FileUpload>

    <!-- Document list -->
    <div v-if="documents.length" class="flex flex-col gap-1.5">
      <p class="text-xs font-semibold text-cape-cod-500 uppercase tracking-wide mb-1 flex items-center gap-1.5">
        <i class="pi pi-folder-open" /> {{ documents.length }} documento{{ documents.length !== 1 ? 's' : '' }}
      </p>
      <div v-for="doc in documents" :key="doc.name" class="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/5 border border-white/10 text-[0.8125rem]">
        <i class="pi pi-file-pdf text-cape-cod-400 text-[0.875rem] shrink-0" v-if="doc.ext === '.pdf'" />
        <i class="pi pi-image text-cape-cod-400 text-[0.875rem] shrink-0" v-else-if="['.png','.jpg','.jpeg'].includes(doc.ext)" />
        <i class="pi pi-file text-cape-cod-400 text-[0.875rem] shrink-0" v-else />
        <span class="flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-cape-cod-400">{{ doc.name }}</span>
        <Tag :value="formatSize(doc.size)" severity="secondary" rounded />
        <Button
          icon="pi pi-trash"
          text
          rounded
          size="small"
          severity="danger"
          class=""
          :loading="deletingDoc === doc.name"
          :disabled="deletingDoc !== null"
          title="Eliminar documento"
          @click="handleDelete(doc.name)"
        />
      </div>
    </div>

    <div v-else-if="!loading" class="flex flex-col items-center gap-1.5 p-4 text-cape-cod-500 text-[0.8125rem]">
      <i class="pi pi-inbox" />
      <span>No hay documentos cargados</span>
    </div>

    <Button
      icon="pi pi-refresh"
      label="Actualizar lista"
      severity="secondary"
      text
      size="small"
      class="self-start !text-cape-cod-500 hover:!text-cape-cod-400"
      :loading="loading"
      @click="fetchDocuments"
    />
  </div>
</template>

