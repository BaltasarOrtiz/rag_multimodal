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
  <div class="upload-panel glass-card">
    <div class="panel-header">
      <i class="pi pi-cloud-upload" />
      <h3>Documentos</h3>
      <span v-if="collectionStore.activeCollection" class="col-chip">
        <i class="pi pi-th-large" /> {{ collectionStore.activeCollection }}
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
        root: { class: 'file-upload-root' },
        buttonbar: { class: 'file-upload-bar' },
        content: { class: 'file-upload-content' },
      }"
    >
      <template #empty>
        <div class="drop-zone">
          <i class="pi pi-file-arrow-up drop-icon" />
          <p class="drop-text">Arrastrá PDFs, imágenes o texto</p>
          <p class="drop-hint">Máx. 50 MB por archivo</p>
        </div>
      </template>
    </FileUpload>

    <!-- Document list -->
    <div v-if="documents.length" class="doc-list">
      <p class="doc-list-title">
        <i class="pi pi-folder-open" /> {{ documents.length }} documento{{ documents.length !== 1 ? 's' : '' }}
      </p>
      <div v-for="doc in documents" :key="doc.name" class="doc-item">
        <i class="pi pi-file-pdf" v-if="doc.ext === '.pdf'" />
        <i class="pi pi-image" v-else-if="['.png','.jpg','.jpeg'].includes(doc.ext)" />
        <i class="pi pi-file" v-else />
        <span class="doc-name">{{ doc.name }}</span>
        <Tag :value="formatSize(doc.size)" severity="secondary" rounded />
        <Button
          icon="pi pi-trash"
          text
          rounded
          size="small"
          severity="danger"
          class="delete-doc-btn"
          :loading="deletingDoc === doc.name"
          :disabled="deletingDoc !== null"
          title="Eliminar documento"
          @click="handleDelete(doc.name)"
        />
      </div>
    </div>

    <div v-else-if="!loading" class="no-docs">
      <i class="pi pi-inbox" />
      <span>No hay documentos cargados</span>
    </div>

    <Button
      icon="pi pi-refresh"
      label="Actualizar lista"
      severity="secondary"
      text
      size="small"
      class="refresh-btn"
      :loading="loading"
      @click="fetchDocuments"
    />
  </div>
</template>

<style scoped>
.upload-panel {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.panel-header i {
  color: var(--cyan-400);
  font-size: 1rem;
}

.col-chip {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: none;
  letter-spacing: 0;
  background: rgba(34, 211, 238, 0.12);
  color: var(--cyan-400);
  border: 1px solid rgba(34, 211, 238, 0.25);
}

/* Drop zone */
.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2rem 1rem;
  color: var(--text-muted);
}

.drop-icon {
  font-size: 2.5rem;
  color: var(--cyan-500);
  opacity: 0.6;
}

.drop-text {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.drop-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Doc list */
.doc-list {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.doc-list-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.625rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-subtle);
  font-size: 0.8125rem;
}

.doc-item i {
  color: var(--cyan-400);
  font-size: 0.875rem;
  flex-shrink: 0;
}

.doc-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}

.no-docs {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.375rem;
  padding: 1rem;
  color: var(--text-muted);
  font-size: 0.8125rem;
}

.refresh-btn {
  align-self: flex-start;
  color: var(--text-muted) !important;
}

/* FileUpload root styling */
:deep(.file-upload-root) {
  width: 100%;
  background: transparent !important;
  border: 1px dashed var(--border-subtle) !important;
  border-radius: 12px !important;
  transition: border-color 0.2s;
}

:deep(.file-upload-root:hover) {
  border-color: var(--cyan-500) !important;
}

:deep(.file-upload-bar) {
  background: transparent !important;
  border: none !important;
  border-bottom: 1px solid var(--border-subtle) !important;
  padding: 0.625rem 0.875rem !important;
}

:deep(.file-upload-content) {
  padding: 0 !important;
}
</style>
