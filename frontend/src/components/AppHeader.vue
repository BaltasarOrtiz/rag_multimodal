<script setup lang="ts">
import { useHealth } from '@/composables/useRag'
import { useCollectionStore } from '@/stores/useCollectionStore'

const { status, indexLoaded } = useHealth()
const collectionStore = useCollectionStore()
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <!-- Logo -->
      <div class="logo">
        <div class="logo-icon">
          <i class="pi pi-database" />
        </div>
        <div class="logo-text">
          <span class="logo-title gradient-text">RAG Multimodal</span>
          <span class="logo-sub">LlamaIndex · Gemini · Qdrant</span>
        </div>
      </div>

      <!-- Centro: colección activa -->
      <div class="active-collection" v-if="collectionStore.activeCollection">
        <i class="pi pi-th-large" />
        <span class="collection-name">{{ collectionStore.activeCollection }}</span>
        <span v-if="collectionStore.activeInfo?.is_default" class="default-badge">default</span>
      </div>

      <!-- Status badge -->
      <div class="header-right">
        <div class="status-pill" :class="status">
          <span class="status-dot" />
          <span v-if="status === 'loading'">Conectando…</span>
          <span v-else-if="status === 'ok'">
            API OK · Index {{ indexLoaded ? 'cargado' : 'vacío' }}
          </span>
          <span v-else>API sin conexión</span>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(10, 10, 15, 0.85);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border-subtle);
}

.header-inner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1.5rem;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.875rem;
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, var(--cyan-500), var(--violet-500));
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.125rem;
  color: white;
  box-shadow: 0 0 20px rgba(34, 211, 238, 0.3);
}

.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.logo-title {
  font-size: 1.125rem;
  font-weight: 700;
}

.logo-sub {
  font-size: 0.6875rem;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

/* Colección activa centrada */
.active-collection {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.85rem;
  border-radius: 8px;
  background: rgba(34, 211, 238, 0.06);
  border: 1px solid rgba(34, 211, 238, 0.18);
  font-size: 0.8125rem;
  color: var(--cyan-400);
  font-weight: 500;
  letter-spacing: 0.01em;
}

.active-collection i {
  font-size: 0.75rem;
  opacity: 0.8;
}

.collection-name {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.default-badge {
  font-size: 0.6rem;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  background: rgba(34, 211, 238, 0.15);
  color: var(--cyan-400);
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

/* Status pill */
.status-pill {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.875rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 500;
  border: 1px solid var(--border-subtle);
  background: var(--bg-card);
  transition: all 0.3s ease;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-pill.loading .status-dot {
  background: var(--warning);
  animation: pulse 1.4s ease-in-out infinite;
}

.status-pill.ok .status-dot {
  background: var(--success);
  box-shadow: 0 0 8px var(--success);
}

.status-pill.error .status-dot {
  background: var(--error);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* Responsive: esconder label de colección en pantallas pequeñas */
@media (max-width: 700px) {
  .active-collection {
    display: none;
  }
}
</style>
