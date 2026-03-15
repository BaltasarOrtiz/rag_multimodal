<script setup lang="ts">
import { ref, computed } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Slider from 'primevue/slider'
import ProgressBar from 'primevue/progressbar'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ragApi from '@/api/ragApi'
import type { EvalQuestion, EvalStatus, EvalQuestionResult } from '@/types/rag'

const toast = useToast()

// ── Estado ────────────────────────────────────────────────────
interface Row {
  id: number
  question: string
  ground_truth: string
}

let _nextId = 1
const rows = ref<Row[]>([
  { id: _nextId++, question: '', ground_truth: '' },
])
const topK = ref(5)

const running = ref(false)
const currentJob = ref<EvalStatus | null>(null)

// ── Filas ─────────────────────────────────────────────────────
function addRow() {
  rows.value.push({ id: _nextId++, question: '', ground_truth: '' })
}

function removeRow(id: number) {
  if (rows.value.length === 1) return
  rows.value = rows.value.filter(r => r.id !== id)
}

function importJson() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    try {
      const text = await file.text()
      const data: Array<{ question: string; ground_truth: string }> = JSON.parse(text)
      if (!Array.isArray(data)) throw new Error('El JSON debe ser un array.')
      rows.value = data.map(d => ({
        id: _nextId++,
        question: d.question ?? '',
        ground_truth: d.ground_truth ?? '',
      }))
      toast.add({ severity: 'success', summary: 'Importado', detail: `${data.length} preguntas cargadas`, life: 3000 })
    } catch (e: any) {
      toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 4000 })
    }
  }
  input.click()
}

// ── Validación ────────────────────────────────────────────────
const validRows = computed(() =>
  rows.value.filter(r => r.question.trim() && r.ground_truth.trim())
)
const canRun = computed(() => validRows.value.length > 0 && !running.value)

// ── Evaluación ────────────────────────────────────────────────
async function runEval() {
  if (!canRun.value) return
  running.value = true
  currentJob.value = null

  const questions: EvalQuestion[] = validRows.value.map(r => ({
    question: r.question.trim(),
    ground_truth: r.ground_truth.trim(),
  }))

  try {
    const { eval_id } = await ragApi.startEval({ questions, top_k: topK.value })
    pollStatus(eval_id)
  } catch (e: any) {
    const detail = e?.response?.data?.detail ?? 'Error al iniciar evaluación'
    toast.add({ severity: 'error', summary: 'Error', detail, life: 5000 })
    running.value = false
  }
}

function pollStatus(evalId: string) {
  setTimeout(async () => {
    try {
      const status = await ragApi.getEvalStatus(evalId)
      currentJob.value = status
      if (status.status === 'running') {
        pollStatus(evalId)
      } else {
        running.value = false
        if (status.status === 'done') {
          toast.add({ severity: 'success', summary: 'Evaluación completada', detail: `${status.n_questions} preguntas evaluadas`, life: 4000 })
        } else {
          toast.add({ severity: 'error', summary: 'Evaluación fallida', detail: status.error ?? 'Error desconocido', life: 5000 })
        }
      }
    } catch {
      running.value = false
    }
  }, 2000)
}

// ── Helpers visuales ─────────────────────────────────────────
function scoreColor(v: number): string {
  if (v >= 0.8) return 'score-high'
  if (v >= 0.5) return 'score-mid'
  return 'score-low'
}

function pct(v: number): string {
  return (v * 100).toFixed(1) + '%'
}

const metricLabels: Record<string, string> = {
  faithfulness: 'Faithfulness',
  answer_relevancy: 'Answer Relevancy',
  context_recall: 'Context Recall',
  context_precision: 'Context Precision',
}

const metricIcons: Record<string, string> = {
  faithfulness: 'pi-check-circle',
  answer_relevancy: 'pi-comments',
  context_recall: 'pi-search',
  context_precision: 'pi-filter',
}

const metricDesc: Record<string, string> = {
  faithfulness: 'La respuesta está soportada por el contexto',
  answer_relevancy: 'La respuesta responde la pregunta',
  context_recall: 'Los chunks contienen el ground truth',
  context_precision: 'Los chunks recuperados son relevantes',
}

function exportResults() {
  if (!currentJob.value?.results) return
  const data = JSON.stringify({
    timestamp: currentJob.value.timestamp,
    n_questions: currentJob.value.n_questions,
    top_k: currentJob.value.top_k,
    metrics: currentJob.value.metrics,
    results: currentJob.value.results,
  }, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `eval_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="eval-panel">

    <!-- ── Encabezado ──────────────────────────────────────── -->
    <div class="eval-header">
      <div class="eval-title-row">
        <i class="pi pi-chart-bar eval-icon" />
        <div>
          <h2 class="eval-title">Evaluación RAG</h2>
          <p class="eval-subtitle">Mide faithfulness, relevancy, context recall y precision usando Gemini como juez</p>
        </div>
      </div>
    </div>

    <!-- ── Configuración + preguntas ─────────────────────────── -->
    <div class="eval-body">

      <!-- Top-K + acciones -->
      <div class="config-row">
        <div class="topk-group">
          <label class="field-label">Top-K <span class="value-badge">{{ topK }}</span></label>
          <Slider v-model="topK" :min="1" :max="15" :step="1" class="topk-slider" :disabled="running" />
        </div>
        <div class="action-btns">
          <Button
            icon="pi pi-upload"
            label="Importar JSON"
            text
            size="small"
            class="!text-cape-cod-400"
            :disabled="running"
            @click="importJson"
          />
          <Button
            icon="pi pi-plus"
            label="Añadir pregunta"
            text
            size="small"
            class="!text-cape-cod-300"
            :disabled="running"
            @click="addRow"
          />
        </div>
      </div>

      <!-- Tabla de preguntas -->
      <div class="questions-list">
        <TransitionGroup name="row">
          <div v-for="row in rows" :key="row.id" class="question-row">
            <div class="row-number">{{ rows.indexOf(row) + 1 }}</div>

            <div class="row-fields">
              <div class="field-group">
                <label class="field-sublabel"><i class="pi pi-question-circle" /> Pregunta</label>
                <InputText
                  v-model="row.question"
                  placeholder="¿Qué quieres preguntar al RAG?"
                  class="row-input"
                  :disabled="running"
                />
              </div>
              <div class="field-group">
                <label class="field-sublabel"><i class="pi pi-check-square" /> Ground truth</label>
                <Textarea
                  v-model="row.ground_truth"
                  placeholder="Respuesta esperada o de referencia..."
                  class="row-textarea"
                  rows="2"
                  auto-resize
                  :disabled="running"
                />
              </div>
            </div>

            <Button
              icon="pi pi-times"
              text
              rounded
              size="small"
              class="remove-btn"
              :disabled="running || rows.length === 1"
              @click="removeRow(row.id)"
            />
          </div>
        </TransitionGroup>
      </div>

      <!-- Botón principal -->
      <Button
        :label="running ? `Evaluando ${currentJob?.questions_done ?? 0}/${currentJob?.n_questions ?? validRows.length}…` : `Evaluar ${validRows.length} pregunta${validRows.length !== 1 ? 's' : ''}`"
        icon="pi pi-play"
        :loading="running"
        :disabled="!canRun"
        class="run-btn"
        @click="runEval"
      />

      <!-- Progreso -->
      <Transition name="fade">
        <div v-if="running && currentJob" class="progress-section">
          <ProgressBar :value="currentJob.progress" class="eval-progress" />
          <span class="progress-label">{{ currentJob.questions_done }} / {{ currentJob.n_questions }} preguntas</span>
        </div>
      </Transition>
    </div>

    <!-- ── Resultados ─────────────────────────────────────────── -->
    <Transition name="fade">
      <div v-if="currentJob?.status === 'done' && currentJob.metrics" class="results-section">

        <div class="results-header">
          <span class="results-title">Resultados</span>
          <Button
            icon="pi pi-download"
            label="Exportar"
            text
            size="small"
            class="!text-cape-cod-400"
            @click="exportResults"
          />
        </div>

        <!-- Métricas agregadas -->
        <div class="metrics-grid">
          <div
            v-for="(_, key) in metricLabels"
            :key="key"
            class="metric-card"
          >
            <div class="metric-top">
              <i :class="`pi ${metricIcons[key]} metric-icon`" />
              <span class="metric-name">{{ metricLabels[key] }}</span>
            </div>
            <div
              class="metric-score"
              :class="scoreColor((currentJob.metrics as any)[key])"
            >
              {{ pct((currentJob.metrics as any)[key]) }}
            </div>
            <div class="metric-bar-track">
              <div
                class="metric-bar-fill"
                :class="scoreColor((currentJob.metrics as any)[key])"
                :style="{ width: pct((currentJob.metrics as any)[key]) }"
              />
            </div>
            <span class="metric-desc">{{ metricDesc[key] }}</span>
          </div>
        </div>

        <!-- Detalle por pregunta -->
        <div class="detail-section">
          <span class="detail-title">Detalle por pregunta</span>
          <DataTable
            :value="currentJob.results ?? []"
            class="eval-table"
            size="small"
            scroll-height="400px"
            scrollable
          >
            <Column field="question" header="Pregunta" style="min-width: 200px">
              <template #body="{ data }: { data: EvalQuestionResult }">
                <span class="cell-question">{{ data.question }}</span>
              </template>
            </Column>
            <Column header="Fidelidad" style="width: 100px">
              <template #body="{ data }: { data: EvalQuestionResult }">
                <span class="cell-score" :class="scoreColor(data.faithfulness)">{{ pct(data.faithfulness) }}</span>
              </template>
            </Column>
            <Column header="Relevancia" style="width: 100px">
              <template #body="{ data }: { data: EvalQuestionResult }">
                <span class="cell-score" :class="scoreColor(data.answer_relevancy)">{{ pct(data.answer_relevancy) }}</span>
              </template>
            </Column>
            <Column header="Recall ctx" style="width: 100px">
              <template #body="{ data }: { data: EvalQuestionResult }">
                <span class="cell-score" :class="scoreColor(data.context_recall)">{{ pct(data.context_recall) }}</span>
              </template>
            </Column>
            <Column header="Precisión ctx" style="width: 110px">
              <template #body="{ data }: { data: EvalQuestionResult }">
                <span class="cell-score" :class="scoreColor(data.context_precision)">{{ pct(data.context_precision) }}</span>
              </template>
            </Column>
            <Column field="nodes_retrieved" header="Nodos" style="width: 80px" />
          </DataTable>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.eval-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* Header */
.eval-header {
  padding: 1.5rem 1.5rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
}
.eval-title-row {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}
.eval-icon {
  font-size: 1.5rem;
  color: var(--text-secondary);
  margin-top: 0.125rem;
  flex-shrink: 0;
}
.eval-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.25rem;
}
.eval-subtitle {
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.4;
}

/* Body */
.eval-body {
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.config-row {
  display: flex;
  align-items: flex-end;
  gap: 1.5rem;
  flex-wrap: wrap;
}
.topk-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 180px;
}
.field-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.value-badge {
  font-size: 0.75rem;
  color: var(--text-secondary);
  background: rgba(160, 168, 171, 0.1);
  border: 1px solid rgba(160, 168, 171, 0.25);
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  font-weight: 400;
}
.topk-slider { width: 100%; }

.action-btns {
  display: flex;
  gap: 0.5rem;
  margin-left: auto;
}

/* Preguntas */
.questions-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 420px;
  overflow-y: auto;
  padding-right: 0.25rem;
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.08) transparent;
}

.question-row {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  background: rgba(255,255,255,0.025);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
}
.row-number {
  font-size: 0.75rem;
  color: var(--text-muted);
  min-width: 1.25rem;
  padding-top: 0.5rem;
  text-align: center;
}
.row-fields {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}
.field-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.field-sublabel {
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.row-input {
  width: 100%;
  font-size: 0.875rem;
}
.row-textarea {
  width: 100%;
  font-size: 0.8125rem;
  resize: none;
}
.remove-btn {
  color: var(--text-muted) !important;
  margin-top: 0.25rem;
  flex-shrink: 0;
}
.remove-btn:hover { color: #f87171 !important; }

/* Botón run */
.run-btn {
  width: 100%;
  justify-content: center;
  font-size: 0.9375rem;
  font-weight: 600;
}

/* Progreso */
.progress-section {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}
.eval-progress { height: 6px; border-radius: 999px; }
.progress-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-align: right;
}

/* Resultados */
.results-section {
  border-top: 1px solid var(--border-subtle);
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.results-title {
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--text-primary);
}

/* Métricas grid */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.875rem;
}
.metric-card {
  padding: 1rem;
  background: rgba(255,255,255,0.025);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}
.metric-top {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.metric-icon {
  font-size: 0.875rem;
  color: var(--text-secondary);
}
.metric-name {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
}
.metric-score {
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1;
}
.metric-bar-track {
  height: 4px;
  background: rgba(255,255,255,0.07);
  border-radius: 999px;
  overflow: hidden;
}
.metric-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.6s ease;
}
.metric-desc {
  font-size: 0.7rem;
  color: var(--text-muted);
  line-height: 1.3;
}

/* Score colors — usa las variables de estado del sistema */
.score-high { color: var(--success); }
.metric-bar-fill.score-high { background: var(--success); }
.score-mid { color: var(--warning); }
.metric-bar-fill.score-mid { background: var(--warning); }
.score-low { color: var(--error); }
.metric-bar-fill.score-low { background: var(--error); }

/* Tabla detalle */
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}
.detail-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.eval-table { font-size: 0.8125rem; }
.cell-question {
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.cell-score {
  font-weight: 700;
  font-size: 0.875rem;
}

/* Transitions */
.fade-enter-active, .fade-leave-active { transition: all 0.25s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(6px); }

.row-enter-active, .row-leave-active { transition: all 0.2s ease; }
.row-enter-from { opacity: 0; transform: translateX(-8px); }
.row-leave-to { opacity: 0; transform: translateX(8px); }

@media (max-width: 640px) {
  .metrics-grid { grid-template-columns: 1fr; }
}
</style>
