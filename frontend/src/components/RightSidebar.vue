<script setup lang="ts">
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import CollectionManager from './CollectionManager.vue'
import DocumentUpload from './DocumentUpload.vue'
import IngestPanel from './IngestPanel.vue'

const tabs = [
  { value: 'collections', icon: 'pi-th-large',    label: 'Base'    },
  { value: 'documents',   icon: 'pi-folder-open', label: 'Docs'    },
  { value: 'ingest',      icon: 'pi-bolt',        label: 'Ingesta' },
]
</script>

<template>
  <!-- Panel principal -->
  <aside
    class="hidden xl:flex w-80 min-w-[320px] shrink-0 flex-col border-l border-white/6 bg-[#0f0f0f] overflow-hidden"
  >
    <Tabs value="documents" class="rs-tabs">

      <TabList class="rs-tablist">
        <Tab
          v-for="tab in tabs"
          :key="tab.value"
          :value="tab.value"
          :pt="{
            root: ({ context }: any) => ({
              class: ['rs-tab', context.active ? 'rs-tab--active' : 'rs-tab--idle']
            })
          }"
        >
          <i :class="`pi ${tab.icon}`" />
          <span>{{ tab.label }}</span>
        </Tab>
      </TabList>

      <TabPanels class="rs-panels">
        <TabPanel value="collections" class="rs-panel">
          <CollectionManager />
        </TabPanel>
        <TabPanel value="documents" class="rs-panel">
          <DocumentUpload />
        </TabPanel>
        <TabPanel value="ingest" class="rs-panel">
          <IngestPanel />
        </TabPanel>
      </TabPanels>

    </Tabs>
  </aside>
</template>

<style scoped>
/* ── Tabs wrapper ──────────────────────────────────────────── */
:deep(.rs-tabs) {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent;
}

/* ── Tab bar ───────────────────────────────────────────────── */
:deep(.rs-tablist) {
  flex-shrink: 0;
  background: #0f0f0f;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0;
  padding: 0;
}

:deep(.p-tablist-tab-list) {
  display: flex;
  width: 100%;
  background: transparent;
  border: none;
  padding: 0;
  gap: 0;
}

/* Ocultar la barra deslizante nativa */
:deep(.p-tablist-active-bar) {
  display: none !important;
}

/* ── Tab individual ────────────────────────────────────────── */
:deep(.rs-tab) {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.9rem 0.4rem;
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  border: none !important;
  border-radius: 0 !important;
  background: transparent !important;
  cursor: pointer;
  position: relative;
  outline: none;
  transition: color 0.15s ease;
}

:deep(.rs-tab .pi) {
  font-size: 0.8rem;
}

:deep(.rs-tab--active) {
  color: #f4f5f5;
  background: rgba(255, 255, 255, 0.03) !important;
}

/* Indicador activo */
:deep(.rs-tab--active::after) {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: rgba(37, 99, 235, 0.9);
  border-radius: 2px 2px 0 0;
}

:deep(.rs-tab--idle) {
  color: #70787b; /* cape-cod-500 */
}

:deep(.rs-tab--idle:hover) {
  color: #a0a8ab; /* cape-cod-400 */
  background: rgba(255, 255, 255, 0.03) !important;
}

/* ── Panels ────────────────────────────────────────────────── */
:deep(.rs-panels) {
  flex: 1;
  overflow-y: auto;
  background: transparent;
  padding: 1.1rem;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.07) transparent;
}

:deep(.rs-panel) {
  padding: 0;
}
</style>
