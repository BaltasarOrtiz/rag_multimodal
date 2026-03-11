<script setup lang="ts">
import ConfirmDialog from 'primevue/confirmdialog'
import DocumentUpload from '@/components/DocumentUpload.vue'
import IngestPanel from '@/components/IngestPanel.vue'
import QueryPanel from '@/components/QueryPanel.vue'
import AppHeader from '@/components/AppHeader.vue'
import CollectionManager from '@/components/CollectionManager.vue'
</script>

<template>
  <div class="home-layout">
    <ConfirmDialog />
    <AppHeader />

    <main class="main-content">
      <div class="sidebar">
        <!-- Gestión de colecciones (en la cima del sidebar) -->
        <CollectionManager />
        <DocumentUpload />
        <IngestPanel />
      </div>

      <section class="query-section">
        <QueryPanel />
      </section>
    </main>

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
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  padding: 1.5rem;
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 1.5rem;
  align-items: start;
}

.sidebar {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 80px;
  max-height: calc(100vh - 96px);
  overflow-y: auto;
  padding-right: 2px;
}

.query-section {
  min-height: calc(100vh - 160px);
}

/* Footer */
.app-footer {
  text-align: center;
  padding: 1.25rem;
  font-size: 0.6875rem;
  color: var(--text-muted);
  border-top: 1px solid var(--border-subtle);
  letter-spacing: 0.04em;
}

/* Responsive */
@media (max-width: 900px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
    max-height: none;
  }
}
</style>
