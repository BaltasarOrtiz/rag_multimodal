<script setup lang="ts">
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import { useIngest, useIngestStatus, useHealth } from '@/composables/useRag'
import { useCollectionStore } from '@/stores/useCollectionStore'

const toast = useToast()
const { loading, message, error, ingest } = useIngest()
const { refresh: refreshHealth } = useHealth()
const collectionStore = useCollectionStore()
const { ingestStatus, startPolling } = useIngestStatus()

async function handleIngest(force = false) {
  await ingest(force)
  startPolling()
  if (message.value) {
    toast.add({ severity: 'info', summary: 'Ingestión', detail: message.value, life: 5000 })
    // Refresh health and collection stats after a short delay
    setTimeout(() => { refreshHealth(); collectionStore.fetchCollections() }, 2000)
  }
  if (error.value) {
    toast.add({ severity: 'error', summary: 'Error', detail: error.value, life: 6000 })
  }
}
</script>

<template>
  <div class="ingest-panel glass-card">
    <div class="panel-header">
      <i class="pi pi-bolt" />
      <h3>Ingestión</h3>
      <span v-if="collectionStore.activeCollection" class="col-chip">
        <i class="pi pi-th-large" /> {{ collectionStore.activeCollection }}
      </span>
    </div>

    <p class="panel-description">
      Procesa los documentos subidos, genera summaries con Gemini y los embeddea en Qdrant.
    </p>

    <div class="ingest-actions">
      <Button
        label="Iniciar Ingestión"
        icon="pi pi-play"
        :loading="loading"
        @click="handleIngest(false)"
        class="ingest-btn"
      />
      <Button
        label="Forzar re-ingestión"
        icon="pi pi-refresh"
        severity="warning"
        outlined
        :loading="loading"
        @click="handleIngest(true)"
        size="small"
      />
    </div>

    <ProgressBar v-if="loading" mode="indeterminate" class="progress-bar" />

    <ProgressBar
      v-if="ingestStatus.status === 'running' && ingestStatus.total_docs"
      :value="Math.round((ingestStatus.processed_docs ?? 0) / (ingestStatus.total_docs ?? 1) * 100)"
      class="ingest-progress"
    />
    <span v-if="ingestStatus.total_docs" class="progress-label">
      {{ ingestStatus.processed_docs ?? 0 }} / {{ ingestStatus.total_docs }} documentos
    </span>

    <Message v-if="message && !loading" severity="info" :closable="false" class="msg">
      <i class="pi pi-info-circle" /> {{ message }}
    </Message>

    <div class="ingest-info">
      <div class="info-item">
        <i class="pi pi-brain" />
        <span>LlamaIndex + Gemini Flash</span>
      </div>
      <div class="info-item">
        <i class="pi pi-server" />
        <span>Vector Store: Qdrant</span>
      </div>
      <div class="info-item">
        <i class="pi pi-sliders-h" />
        <span>Chunk: 512 tokens · Overlap: 64</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ingest-panel {
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
  flex-wrap: wrap;
}

.panel-header i {
  color: var(--violet-400);
  font-size: 1rem;
}

.col-chip {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.65rem;
  padding: 0.15rem 0.5rem;
  border-radius: 6px;
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(139, 92, 246, 0.2);
  color: var(--violet-400);
  font-weight: 500;
  letter-spacing: 0.02em;
  text-transform: none;
  margin-left: auto;
}

.col-chip i {
  font-size: 0.6rem;
  color: var(--violet-400);
}

.panel-description {
  font-size: 0.8125rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.ingest-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.ingest-btn {
  background: linear-gradient(135deg, var(--cyan-600), var(--violet-600)) !important;
  border: none !important;
  font-weight: 600 !important;
}

.ingest-btn:hover {
  box-shadow: 0 0 20px rgba(34, 211, 238, 0.3) !important;
}

.progress-bar {
  height: 4px !important;
  border-radius: 2px !important;
}

.msg {
  font-size: 0.8125rem;
}

/* Info badges */
.ingest-info {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-subtle);
}

.info-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.info-item i {
  color: var(--violet-400);
  font-size: 0.75rem;
  width: 14px;
}

.ingest-progress {
  height: 6px !important;
  border-radius: 9999px !important;
}

:deep(.ingest-progress .p-progressbar-value) {
  background: var(--cyan-400) !important;
  border-radius: 9999px !important;
}

.progress-label {
  font-size: 0.725rem;
  color: var(--text-muted);
  text-align: right;
}
</style>
