<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import { useToast } from 'primevue/usetoast'
import { useIngest, useIngestStatus, useHealth } from '@/composables/useRag'
import { useCollectionStore } from '@/stores/useCollectionStore'

const toast = useToast()
const { loading, message, error, ingest } = useIngest()
const { refresh: refreshHealth } = useHealth()
const collectionStore = useCollectionStore()
const { ingestStatus, startPolling } = useIngestStatus()

interface LastIngestResult {
  ok: boolean
  text: string
  time: string
}
const lastResult = ref<LastIngestResult | null>(null)

async function handleIngest(force = false) {
  await ingest(force)
  startPolling()
  if (message.value) {
    toast.add({ severity: 'info', summary: 'Ingestión', detail: message.value, life: 5000 })
    lastResult.value = { ok: true, text: message.value, time: new Date().toLocaleTimeString() }
    setTimeout(() => { refreshHealth(); collectionStore.fetchCollections() }, 2000)
  }
  if (error.value) {
    toast.add({ severity: 'error', summary: 'Error', detail: error.value, life: 6000 })
    lastResult.value = { ok: false, text: error.value, time: new Date().toLocaleTimeString() }
  }
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <div v-if="collectionStore.activeCollection" class="flex items-center gap-1.5 text-[0.7rem] font-semibold text-cape-cod-400 bg-cape-cod-400/10 border border-cape-cod-400/20 rounded-full px-2.5 py-1 self-start">
      <i class="pi pi-th-large text-[0.6rem]" /> {{ collectionStore.activeCollection }}
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
        class="bg-gradient-to-br from-cape-cod-300 to-cape-cod-500 !border-none !font-semibold !text-cape-cod-950 hover:brightness-110"
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

    <!-- Persistent last-ingest status -->
    <Transition name="status-fade">
      <div
        v-if="lastResult && !loading"
        class="flex items-start gap-2.5 px-3 py-2.5 rounded-lg border text-[0.7875rem] leading-snug"
        :class="lastResult.ok
          ? 'bg-green-500/5 border-green-500/20 text-green-400'
          : 'bg-red-500/5 border-red-500/20 text-red-400'"
      >
        <i
          class="text-sm mt-[0.05rem] shrink-0"
          :class="lastResult.ok ? 'pi pi-check-circle' : 'pi pi-times-circle'"
        />
        <div class="flex-1 min-w-0">
          <p class="m-0 font-medium">{{ lastResult.ok ? 'Ingestión completada' : 'Ingestión fallida' }}</p>
          <p class="m-0 opacity-80 text-[0.7rem] mt-0.5 truncate">{{ lastResult.text }}</p>
        </div>
        <span class="text-[0.65rem] opacity-50 shrink-0 mt-[0.1rem]">{{ lastResult.time }}</span>
      </div>
    </Transition>

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
.status-fade-enter-active, .status-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.status-fade-enter-from, .status-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
