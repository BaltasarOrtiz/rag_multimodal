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
  <div class="home-layout">
    <ConfirmDialog />
    <AppHeader />

    <div class="main-content">
      <!-- Sidebar izquierdo: historial de conversaciones -->
      <ConversationSidebar v-model:collapsed="sidebarCollapsed" />

      <!-- Columna central: chat -->
      <section class="center-column">
        <QueryPanel />
      </section>

      <!-- Sidebar derecho: documentos/ingestión -->
      <aside class="right-sidebar">
        <CollectionManager />
        <DocumentUpload />
        <IngestPanel />
      </aside>
    </div>

    <!-- Footer -->
    <footer class="app-footer">
      <span>LlamaIndex · Gemini 2.5 Flash · Qdrant · FastAPI · Vue 3 + PrimeVue</span>
    </footer>
  </div>
</template>

<style scoped>
.home-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
  height: calc(100vh - 64px - 48px); /* viewport - header - footer */
}

/* Columna central */
.center-column {
  flex: 1;
  min-width: 0;
  padding: 1rem 1.25rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Sidebar derecho: documentos / ingestión */
.right-sidebar {
  width: 320px;
  min-width: 280px;
  flex-shrink: 0;
  padding: 1rem 1rem 1rem 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
  border-left: 1px solid var(--border-subtle);
  scrollbar-width: thin;
  scrollbar-color: var(--border-subtle) transparent;
}

/* Footer */
.app-footer {
  text-align: center;
  padding: 0.875rem;
  font-size: 0.6875rem;
  color: var(--text-muted);
  border-top: 1px solid var(--border-subtle);
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

/* Responsive: pantallas medianas — ocultar right-sidebar */
@media (max-width: 1100px) {
  .right-sidebar {
    display: none;
  }
}

/* Responsive: móvil */
@media (max-width: 767px) {
  .main-content {
    height: auto;
    flex-direction: column;
  }

  .center-column {
    padding: 0.75rem;
  }
}
</style>
