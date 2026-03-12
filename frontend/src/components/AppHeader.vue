<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import Select from 'primevue/select'
import Button from 'primevue/button'
import { useHealth } from '@/composables/useRag'
import { useCollectionStore } from '@/stores/useCollectionStore'

const router = useRouter()
const { status, indexLoaded } = useHealth()
const collectionStore = useCollectionStore()

const collectionOptions = computed(() =>
  collectionStore.collections.map(c => ({
    label: c.is_default ? `${c.name} ★` : c.name,
    value: c.name,
  }))
)

function onCollectionChange(name: string) {
  collectionStore.setActive(name)
}
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

      <!-- Centro: selector de colección activa -->
      <Select
        :model-value="collectionStore.activeCollection"
        :options="collectionOptions"
        option-label="label"
        option-value="value"
        placeholder="Colección..."
        class="collection-select"
        :disabled="!collectionOptions.length"
        @change="onCollectionChange($event.value)"
      />

      <!-- Acciones del header -->
      <div class="header-right">
        <!-- Botón de configuraciones -->
        <Button
          icon="pi pi-cog"
          text
          rounded
          class="settings-btn"
          title="Configuraciones"
          @click="router.push('/settings')"
        />

        <!-- Status badge -->
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

/* Selector de colección */
.collection-select {
  min-width: 160px;
  max-width: 220px;
  font-size: 0.8rem;
}
:deep(.collection-select .p-select) {
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  color: var(--text-primary);
  padding: 0.25rem 0.5rem;
  font-size: 0.8rem;
}
:deep(.collection-select .p-select:hover) {
  border-color: rgba(34,211,238,0.4);
}
:deep(.collection-select .p-select-label) {
  color: var(--cyan-400);
  font-weight: 500;
}
:deep(.p-select-overlay .p-select-option.p-selected) {
  background: rgba(34,211,238,0.1);
  color: var(--cyan-400);
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

/* Settings button */
.settings-btn {
  color: var(--text-muted) !important;
  flex-shrink: 0;
}
.settings-btn:hover {
  color: var(--cyan-400) !important;
}

/* Responsive: esconder selector de colección en pantallas pequeñas */
@media (max-width: 700px) {
  .collection-select {
    display: none;
  }
}
</style>
