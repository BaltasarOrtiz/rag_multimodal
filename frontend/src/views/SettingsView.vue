<script setup lang="ts">
import AppHeader from '@/components/AppHeader.vue'
import SettingsPanel from '@/components/SettingsPanel.vue'
</script>

<template>
  <div class="settings-layout">
    <AppHeader />

    <main class="settings-main">
      <div class="settings-container">
        <div class="settings-title-row">
          <i class="pi pi-cog settings-icon" />
          <h1 class="settings-title">Configuraciones</h1>
        </div>
        <SettingsPanel />
      </div>
    </main>

    <footer class="app-footer">
      <span>LlamaIndex · Gemini 2.5 Flash · Qdrant · FastAPI · Vue 3 + PrimeVue</span>
    </footer>
  </div>
</template>

<style scoped>
.settings-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.settings-main {
  flex: 1;
  padding: 2rem 1.5rem;
  display: flex;
  justify-content: center;
}

.settings-container {
  width: 100%;
  max-width: 760px;
}

.settings-title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.settings-icon {
  font-size: 1.375rem;
  color: var(--text-secondary);
}

.settings-title {
  font-size: 1.375rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.app-footer {
  text-align: center;
  padding: 0.875rem;
  font-size: 0.6875rem;
  color: var(--text-muted);
  border-top: 1px solid var(--border-subtle);
  letter-spacing: 0.04em;
}
</style>
