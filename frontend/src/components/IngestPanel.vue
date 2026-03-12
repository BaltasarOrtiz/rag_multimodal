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
  <div class="p-5 flex flex-col gap-4 bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl transition-all duration-200 hover:bg-white/10 hover:border-cape-cod-600/30">
    <div class="flex items-center gap-2.5 text-sm font-semibold text-cape-cod-400 uppercase tracking-wide flex-wrap">
      <i class="pi pi-bolt text-cape-cod-300 text-base" />
      <h3>Ingestión</h3>
      <span v-if="collectionStore.activeCollection" class="ml-auto flex items-center gap-1 text-[0.65rem] py-0.5 px-2 rounded-md bg-cape-cod-400/10 border border-cape-cod-400/20 text-cape-cod-300 font-medium tracking-wide">
        <i class="pi pi-th-large text-[0.6rem] text-cape-cod-300" /> {{ collectionStore.activeCollection }}
      </span>
    </div>

    <p class="text-[0.8125rem] text-cape-cod-500 leading-relaxed">
      Procesa los documentos subidos, genera summaries con Gemini y los embeddea en Qdrant.
    </p>

    <div class="flex flex-col gap-2">
      <Button
        label="Iniciar Ingestión"
        icon="pi pi-play"
        :loading="loading"
        @click="handleIngest(false)"
        class="bg-gradient-to-br from-cape-cod-600 to-cape-cod-800 !border-none !font-semibold hover:shadow-[0_0_20px_rgba(81,89,92,0.3)]"
      />
      <Button
        label="Forzar re-ingestión"
        icon="pi pi-refresh"
        severity="warn"
        outlined
        :loading="loading"
        @click="handleIngest(true)"
        size="small"
      />
    </div>

    <ProgressBar v-if="loading" mode="indeterminate" class="!h-1 !rounded-sm" />

    <ProgressBar
      v-if="ingestStatus.status === 'running' && ingestStatus.total_docs"
      :value="Math.round((ingestStatus.processed_docs ?? 0) / (ingestStatus.total_docs ?? 1) * 100)"
      class="!h-1.5 !rounded-full"
    />
    <span v-if="ingestStatus.total_docs" class="text-[0.725rem] text-cape-cod-500 text-right">
      {{ ingestStatus.processed_docs ?? 0 }} / {{ ingestStatus.total_docs }} documentos
    </span>

    <Message v-if="message && !loading" severity="info" :closable="false" class="text-[0.8125rem]">
      <i class="pi pi-info-circle mr-1" /> {{ message }}
    </Message>

    <div class="flex flex-col gap-1.5 pt-2 border-t border-white/10">
      <div class="flex items-center gap-2 text-xs text-cape-cod-500">
        <i class="pi pi-brain text-cape-cod-400 text-xs w-3.5" />
        <span>LlamaIndex + Gemini Flash</span>
      </div>
      <div class="flex items-center gap-2 text-xs text-cape-cod-500">
        <i class="pi pi-server text-cape-cod-400 text-xs w-3.5" />
        <span>Vector Store: Qdrant</span>
      </div>
      <div class="flex items-center gap-2 text-xs text-cape-cod-500">
        <i class="pi pi-sliders-h text-cape-cod-400 text-xs w-3.5" />
        <span>Chunk: 512 tokens · Overlap: 64</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.p-progressbar-value) {
  background: var(--p-primary-400) !important;
  border-radius: 9999px !important;
}
</style>
