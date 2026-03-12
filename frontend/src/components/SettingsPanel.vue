<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import Slider from 'primevue/slider'
import { useHealth } from '@/composables/useRag'
import ragApi from '@/api/ragApi'
import type { RagConfig } from '@/types/rag'

const toast = useToast()
const { status, indexLoaded } = useHealth()

// ── Estado ────────────────────────────────────────────────────
const config = ref<RagConfig>({
  llm_model: 'gemini-2.5-flash',
  embedding_model: 'models/gemini-embedding-2-preview',
  enable_hybrid: true,
  enable_reranker: true,
  enable_hyde: false,
  enable_semantic_chunking: false,
  reranker_model: 'cross-encoder/ms-marco-MiniLM-L-2-v2',
  hybrid_alpha: 0.5,
  embedding_dim: 3072,
})
const saving = ref(false)

// ── Opciones de selectores ──────────────────────────────────
const llmOptions = [
  { label: 'gemini-2.5-flash (recomendado, más rápido)',  value: 'gemini-2.5-flash' },
  { label: 'gemini-2.5-pro (mayor calidad)',              value: 'gemini-2.5-pro' },
  { label: 'gemini-2.0-flash',                            value: 'gemini-2.0-flash' },
  { label: 'gemini-2.0-flash-lite',                       value: 'gemini-2.0-flash-lite' },
  { label: 'gemini-1.5-pro',                              value: 'gemini-1.5-pro' },
  { label: 'gemini-1.5-flash',                            value: 'gemini-1.5-flash' },
]

const embeddingOptions = [
  { label: 'models/gemini-embedding-2-preview (recomendado)', value: 'models/gemini-embedding-2-preview' },
  { label: 'models/text-embedding-004',                       value: 'models/text-embedding-004' },
]

const rerankerOptions = [
  { label: 'ms-marco-MiniLM-L-2-v2 (más rápido)',         value: 'cross-encoder/ms-marco-MiniLM-L-2-v2' },
  { label: 'ms-marco-MiniLM-L-6-v2 (más preciso)',        value: 'cross-encoder/ms-marco-MiniLM-L-6-v2' },
  { label: 'ms-marco-MiniLM-L-12-v2 (mayor calidad)',     value: 'cross-encoder/ms-marco-MiniLM-L-12-v2' },
]

// ── Chips informativos ────────────────────────────────────────
function llmInfo(model: string): string {
  switch (model) {
    case 'gemini-2.5-flash': return 'Contexto 1M tokens · Rápido'
    case 'gemini-2.5-pro':   return 'Mayor calidad · Más lento'
    case 'gemini-2.0-flash': return 'Contexto 1M tokens'
    case 'gemini-2.0-flash-lite': return 'Más económico'
    case 'gemini-1.5-pro':   return 'Contexto 2M tokens'
    case 'gemini-1.5-flash': return 'Contexto 1M tokens'
    default:                 return ''
  }
}

function embeddingInfo(model: string): string {
  if (model === 'models/gemini-embedding-2-preview') return 'Dimensión: 3072'
  if (model === 'models/text-embedding-004') return 'Dimensión: 768'
  return ''
}

// ── Cargar config al montar ─────────────────────────────────
onMounted(async () => {
  try {
    const remote = await ragApi.getConfig()
    config.value = remote
  } catch (e: any) {
    toast.add({ severity: 'warn', summary: 'Aviso', detail: 'No se pudo cargar la configuración del backend', life: 4000 })
  }
})

// ── Guardar con debounce ──────────────────────────────────────
let sliderTimer: ReturnType<typeof setTimeout> | null = null

async function save(patch: Partial<RagConfig>) {
  saving.value = true
  try {
    await ragApi.updateConfig(patch)
    toast.add({ severity: 'success', summary: 'Guardado', detail: 'Configuración actualizada', life: 2500 })
  } catch (e: any) {
    const detail = e?.response?.data?.detail ?? 'Error al guardar configuración'
    toast.add({ severity: 'error', summary: 'Error', detail, life: 4000 })
  } finally {
    saving.value = false
  }
}

function saveField(field: keyof RagConfig, value: unknown) {
  save({ [field]: value })
}

function saveSlider(field: keyof RagConfig, value: unknown) {
  if (sliderTimer) clearTimeout(sliderTimer)
  sliderTimer = setTimeout(() => save({ [field]: value }), 500)
}
</script>

<template>
  <div class="settings-panel glass-card">
    <Tabs value="0">
      <TabList>
        <Tab value="0"><i class="pi pi-cpu" /> Modelos</Tab>
        <Tab value="1"><i class="pi pi-sliders-h" /> Búsqueda RAG</Tab>
        <Tab value="2"><i class="pi pi-info-circle" /> Sistema</Tab>
      </TabList>

      <!-- ─── TAB 1: Modelos ──────────────────────────────── -->
      <TabPanels>
        <TabPanel value="0">
          <div class="tab-content">
            <!-- LLM -->
            <div class="field-group">
              <label class="field-label">Modelo LLM</label>
              <Select
                v-model="config.llm_model"
                :options="llmOptions"
                option-label="label"
                option-value="value"
                class="full-select"
                @change="saveField('llm_model', config.llm_model)"
              />
              <span v-if="llmInfo(config.llm_model)" class="info-chip">
                <i class="pi pi-info-circle" /> {{ llmInfo(config.llm_model) }}
              </span>
            </div>

            <!-- Embedding -->
            <div class="field-group">
              <label class="field-label">Modelo de Embedding</label>
              <Select
                v-model="config.embedding_model"
                :options="embeddingOptions"
                option-label="label"
                option-value="value"
                class="full-select"
                @change="saveField('embedding_model', config.embedding_model)"
              />
              <span v-if="embeddingInfo(config.embedding_model)" class="info-chip">
                <i class="pi pi-info-circle" /> {{ embeddingInfo(config.embedding_model) }}
              </span>
            </div>

            <!-- Warning embedding -->
            <div class="warning-box">
              <i class="pi pi-exclamation-triangle" />
              <span>
                Cambiar el modelo de embedding requiere re-ingestar los documentos
                para regenerar los vectores con el nuevo modelo.
              </span>
            </div>
          </div>
        </TabPanel>

        <!-- ─── TAB 2: Búsqueda RAG ────────────────────── -->
        <TabPanel value="1">
          <div class="tab-content">
            <!-- Búsqueda híbrida -->
            <div class="toggle-row">
              <div class="toggle-info">
                <span class="toggle-label">Búsqueda híbrida</span>
                <span class="toggle-desc">Dense + Sparse (BM25)</span>
              </div>
              <ToggleSwitch
                v-model="config.enable_hybrid"
                @change="saveField('enable_hybrid', config.enable_hybrid)"
              />
            </div>

            <!-- Alpha híbrido (solo si hybrid activo) -->
            <Transition name="fade">
              <div v-if="config.enable_hybrid" class="field-group indent-field">
                <label class="field-label">
                  Alpha híbrido <span class="alpha-hint">Dense ← {{ config.hybrid_alpha.toFixed(2) }} → Sparse</span>
                </label>
                <Slider
                  v-model="config.hybrid_alpha"
                  :min="0"
                  :max="1"
                  :step="0.05"
                  class="rag-slider"
                  @change="saveSlider('hybrid_alpha', config.hybrid_alpha)"
                />
              </div>
            </Transition>

            <!-- Reranker -->
            <div class="toggle-row">
              <div class="toggle-info">
                <span class="toggle-label">Reranker</span>
                <span class="toggle-desc">Cross-encoder para refinar resultados</span>
              </div>
              <ToggleSwitch
                v-model="config.enable_reranker"
                @change="saveField('enable_reranker', config.enable_reranker)"
              />
            </div>

            <!-- Modelo reranker (solo si reranker activo) -->
            <Transition name="fade">
              <div v-if="config.enable_reranker" class="field-group indent-field">
                <label class="field-label">Modelo reranker</label>
                <Select
                  v-model="config.reranker_model"
                  :options="rerankerOptions"
                  option-label="label"
                  option-value="value"
                  class="full-select"
                  @change="saveField('reranker_model', config.reranker_model)"
                />
              </div>
            </Transition>

            <!-- HyDE -->
            <div class="toggle-row">
              <div class="toggle-info">
                <span class="toggle-label">HyDE</span>
                <span class="toggle-desc">Hypothetical Document Embedding</span>
              </div>
              <ToggleSwitch
                v-model="config.enable_hyde"
                @change="saveField('enable_hyde', config.enable_hyde)"
              />
            </div>

            <!-- Chunking semántico -->
            <div class="toggle-row">
              <div class="toggle-info">
                <span class="toggle-label">Chunking semántico</span>
                <span class="toggle-desc">Más preciso pero más lento en ingestión</span>
              </div>
              <ToggleSwitch
                v-model="config.enable_semantic_chunking"
                @change="saveField('enable_semantic_chunking', config.enable_semantic_chunking)"
              />
            </div>
          </div>
        </TabPanel>

        <!-- ─── TAB 3: Sistema ──────────────────────────── -->
        <TabPanel value="2">
          <div class="tab-content">
            <div class="sys-grid">
              <!-- Stack -->
              <div class="sys-card">
                <span class="sys-label"><i class="pi pi-layers" /> Stack</span>
                <span class="sys-value">LlamaIndex · Gemini · Qdrant · FastAPI · Vue 3</span>
              </div>

              <!-- Versión -->
              <div class="sys-card">
                <span class="sys-label"><i class="pi pi-tag" /> Versión</span>
                <span class="sys-value">1.0.0</span>
              </div>

              <!-- Estado API -->
              <div class="sys-card">
                <span class="sys-label"><i class="pi pi-server" /> Estado de la API</span>
                <span class="sys-value" :class="status === 'ok' ? 'status-ok' : 'status-err'">
                  <span class="status-dot" :class="status" />
                  {{ status === 'ok' ? `OK · Index ${indexLoaded ? 'cargado' : 'vacío'}` : status === 'loading' ? 'Conectando…' : 'Sin conexión' }}
                </span>
              </div>

              <!-- Embedding dim -->
              <div class="sys-card">
                <span class="sys-label"><i class="pi pi-database" /> Dimensión de embeddings</span>
                <span class="sys-value">{{ config.embedding_dim }}</span>
              </div>
            </div>
          </div>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
.settings-panel {
  padding: 0;
}

:deep(.p-tabs .p-tablist) {
  background: transparent;
  border-bottom: 1px solid var(--border-subtle);
  padding: 0 1.25rem;
}

:deep(.p-tabs .p-tab) {
  color: var(--text-muted);
  font-size: 0.875rem;
  padding: 0.75rem 1rem;
  gap: 0.375rem;
}

:deep(.p-tabs .p-tab.p-tab-active) {
  color: var(--cyan-400);
  border-bottom-color: var(--cyan-400);
}

:deep(.p-tabs .p-tabpanels) {
  background: transparent;
  padding: 0;
}

:deep(.p-tabs .p-tabpanel) {
  padding: 0;
}

.tab-content {
  padding: 1.5rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* Field groups */
.field-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.field-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.alpha-hint {
  font-size: 0.75rem;
  color: var(--cyan-400);
  font-weight: 400;
}

.full-select {
  width: 100%;
}

:deep(.full-select .p-select) {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  color: var(--text-primary);
}

:deep(.full-select .p-select:hover) {
  border-color: rgba(34, 211, 238, 0.4);
}

:deep(.full-select .p-select-label) {
  font-size: 0.875rem;
}

.info-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.75rem;
  color: var(--cyan-400);
  background: rgba(34, 211, 238, 0.08);
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 9999px;
  padding: 0.2rem 0.625rem;
  width: fit-content;
}

.warning-box {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
  padding: 0.875rem 1rem;
  background: rgba(250, 204, 21, 0.07);
  border: 1px solid rgba(250, 204, 21, 0.25);
  border-radius: 8px;
  font-size: 0.8125rem;
  color: #fde68a;
  line-height: 1.5;
}

.warning-box i {
  color: #facc15;
  font-size: 1rem;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

/* Toggle rows */
.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
}

.toggle-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.toggle-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.toggle-desc {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.indent-field {
  margin-left: 1rem;
  padding-left: 1rem;
  border-left: 2px solid rgba(34, 211, 238, 0.2);
}

.rag-slider {
  width: 100%;
}

/* Sistema */
.sys-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.sys-card {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  padding: 0.875rem 1rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
}

.sys-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.sys-value {
  font-size: 0.875rem;
  color: var(--text-secondary);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.ok { background: var(--success, #4ade80); box-shadow: 0 0 6px #4ade80; }
.status-dot.error { background: var(--error, #f87171); }
.status-dot.loading { background: #facc15; animation: blink 1.2s ease infinite; }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.status-ok { color: #4ade80; }
.status-err { color: #f87171; }

/* Transitions */
.fade-enter-active, .fade-leave-active { transition: all 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(-4px); }

/* Responsive */
@media (max-width: 600px) {
  .sys-grid { grid-template-columns: 1fr; }
}
</style>
