<script setup lang="ts">
import { ref } from 'vue'
import ConfirmDialog from 'primevue/confirmdialog'
import DocumentUpload from '@/components/DocumentUpload.vue'
import IngestPanel from '@/components/IngestPanel.vue'
import QueryPanel from '@/components/QueryPanel.vue'
import AppHeader from '@/components/AppHeader.vue'
import CollectionManager from '@/components/CollectionManager.vue'
import ConversationSidebar from '@/components/ConversationSidebar.vue'

const sidebarCollapsed = ref(false)
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <ConfirmDialog />
    <AppHeader />

    <div class="flex-1 flex flex-col md:flex-row overflow-hidden" style="height: calc(100vh - 64px - 48px);">
      <!-- Sidebar izquierdo: historial de conversaciones -->
      <ConversationSidebar v-model:collapsed="sidebarCollapsed" />

      <!-- Columna central: chat -->
      <section class="flex-1 min-w-0 p-3 md:p-5 overflow-hidden flex flex-col">
        <QueryPanel class="h-full" />
      </section>

      <!-- Sidebar derecho: documentos/ingestión -->
      <aside class="hidden xl:flex w-80 min-w-[280px] shrink-0 pt-4 pr-4 pb-4 flex-col gap-4 overflow-y-auto border-l border-white/10 dark:border-white/10" style="scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.08) transparent;">
        <CollectionManager />
        <DocumentUpload />
        <IngestPanel />
      </aside>
    </div>

    <!-- Footer -->
    <footer class="text-center p-3.5 text-[0.6875rem] text-cape-cod-500 border-t border-white/10 shrink-0 tracking-wider">
      <span>LlamaIndex · Gemini 2.5 Flash · Qdrant · FastAPI · Vue 3 + PrimeVue</span>
    </footer>
  </div>
</template>

