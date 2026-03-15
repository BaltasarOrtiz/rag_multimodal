<script setup lang="ts">
import AppHeader from '@/components/AppHeader.vue'
import EvalPanel from '@/components/EvalPanel.vue'
</script>

<template>
  <div class="eval-layout">
    <AppHeader />

    <main class="eval-main">
      <div class="eval-container glass-card">
        <EvalPanel />
      </div>
    </main>

    <footer class="app-footer">
      <span>LlamaIndex · Gemini 2.5 Flash · Qdrant · FastAPI · Vue 3 + PrimeVue</span>
    </footer>
  </div>
</template>

<style scoped>
.eval-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.eval-main {
  flex: 1;
  padding: 2rem 1.5rem;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.eval-container {
  width: 100%;
  max-width: 860px;
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
