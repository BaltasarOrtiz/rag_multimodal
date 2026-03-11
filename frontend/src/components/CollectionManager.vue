<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Select from 'primevue/select'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Badge from 'primevue/badge'
import { useCollectionStore } from '@/stores/useCollectionStore'

const store = useCollectionStore()
const toast = useToast()
const confirm = useConfirm()

// ── Diálogo crear colección ──
const showCreate = ref(false)
const newName = ref('')
const newDescription = ref('')
const nameError = ref('')
const creating = ref(false)

const NAME_RE = /^[a-z0-9][a-z0-9_-]*$/

function validateName(v: string) {
  if (!v) return 'El nombre es obligatorio.'
  if (v.length < 2) return 'Mínimo 2 caracteres.'
  if (v.length > 64) return 'Máximo 64 caracteres.'
  if (!NAME_RE.test(v)) return 'Solo minúsculas, números, _ y -'
  return ''
}

function openCreate() {
  newName.value = ''
  newDescription.value = ''
  nameError.value = ''
  showCreate.value = true
}

async function submitCreate() {
  nameError.value = validateName(newName.value)
  if (nameError.value) return
  creating.value = true
  try {
    await store.createCollection(newName.value.trim(), newDescription.value.trim())
    toast.add({ severity: 'success', summary: 'Colección creada', detail: `'${newName.value}' lista para usar.`, life: 4000 })
    showCreate.value = false
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: store.error ?? 'Error al crear', life: 5000 })
  } finally {
    creating.value = false
  }
}

// ── Eliminar colección ──
function confirmDelete(name: string, isDefault: boolean) {
  if (isDefault) {
    toast.add({ severity: 'warn', summary: 'Atención', detail: 'No se puede eliminar la colección por defecto.', life: 4000 })
    return
  }
  confirm.require({
    message: `¿Eliminar la colección '${name}'? Se borrarán todos sus documentos y vectores. Esta acción no se puede deshacer.`,
    header: 'Eliminar colección',
    icon: 'pi pi-exclamation-triangle',
    rejectLabel: 'Cancelar',
    acceptLabel: 'Eliminar',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await store.deleteCollection(name)
        toast.add({ severity: 'warn', summary: 'Eliminada', detail: `Colección '${name}' eliminada.`, life: 4000 })
      } catch {
        toast.add({ severity: 'error', summary: 'Error', detail: store.error ?? 'Error al eliminar', life: 5000 })
      }
    },
  })
}

onMounted(() => store.fetchCollections())
</script>

<template>
  <div class="collection-manager glass-card">
    <!-- Header -->
    <div class="cm-header">
      <div class="cm-title">
        <i class="pi pi-th-large" />
        <span>Base de conocimiento</span>
      </div>
      <Button
        icon="pi pi-plus"
        size="small"
        text
        rounded
        v-tooltip.left="'Nueva colección'"
        @click="openCreate"
      />
    </div>

    <!-- Selector de colección activa -->
    <div class="cm-selector">
      <label class="cm-label">Colección activa</label>
      <Select
        :options="store.collections"
        optionLabel="name"
        optionValue="name"
        v-model="store.activeCollection"
        placeholder="Seleccionar colección…"
        class="cm-select"
        :loading="store.loading"
      >
        <template #option="{ option }">
          <div class="col-option">
            <div class="col-option-name">
              <span>{{ option.name }}</span>
              <span v-if="option.is_default" class="col-badge default">default</span>
            </div>
            <div class="col-option-stats">
              <span><i class="pi pi-file-o" /> {{ option.doc_count }}</span>
              <span><i class="pi pi-server" /> {{ option.vector_count.toLocaleString() }}</span>
            </div>
          </div>
        </template>
        <template #value="{ value }">
          <span v-if="value">
            <i class="pi pi-database" style="margin-right: 0.4rem; opacity: 0.6;" />
            {{ value }}
          </span>
          <span v-else class="placeholder">Seleccionar…</span>
        </template>
      </Select>
    </div>

    <!-- Lista de colecciones -->
    <div class="cm-list" v-if="store.collections.length">
      <div
        v-for="col in store.collections"
        :key="col.name"
        class="col-row"
        :class="{ active: col.name === store.activeCollection }"
        @click="store.setActive(col.name)"
      >
        <div class="col-row-info">
          <div class="col-row-name">
            <i class="pi pi-database col-row-icon" :class="{ 'icon-active': col.name === store.activeCollection }" />
            <span class="col-row-label" :title="col.name">{{ col.name }}</span>
            <Badge v-if="col.is_default" value="default" severity="secondary" class="col-default-badge" />
          </div>
          <div class="col-row-desc" v-if="col.description">{{ col.description }}</div>
          <div class="col-row-stats">
            <span class="stat-chip" v-tooltip.bottom="'Documentos'">
              <i class="pi pi-file-o" /> {{ col.doc_count }}
            </span>
            <span class="stat-chip vectors" v-tooltip.bottom="'Vectores indexados'">
              <i class="pi pi-server" /> {{ col.vector_count.toLocaleString() }}
            </span>
          </div>
        </div>
        <Button
          icon="pi pi-trash"
          text
          rounded
          severity="danger"
          size="small"
          v-tooltip.left="col.is_default ? 'No se puede eliminar la colección default' : 'Eliminar colección'"
          :disabled="col.is_default"
          @click.stop="confirmDelete(col.name, col.is_default)"
          class="col-delete-btn"
        />
      </div>
    </div>

    <div v-else-if="!store.loading" class="cm-empty">
      <i class="pi pi-inbox" />
      <span>Sin colecciones. Crea una.</span>
    </div>

    <!-- Botón refresh -->
    <Button
      label="Actualizar"
      icon="pi pi-refresh"
      text
      size="small"
      :loading="store.loading"
      @click="store.fetchCollections()"
      class="cm-refresh"
    />
  </div>

  <!-- Diálogo crear colección -->
  <Dialog
    v-model:visible="showCreate"
    header="Nueva colección"
    modal
    :style="{ width: '28rem' }"
    :closable="!creating"
    class="create-dialog"
  >
    <div class="create-form">
      <div class="form-field">
        <label class="field-label">Nombre <span class="required">*</span></label>
        <InputText
          v-model="newName"
          placeholder="ej: medicina_2024"
          class="field-input"
          :invalid="!!nameError"
          @input="nameError = ''"
          @keyup.enter="submitCreate"
          autofocus
        />
        <small v-if="nameError" class="field-error">{{ nameError }}</small>
        <small v-else class="field-hint">Solo minúsculas, números, _ y -</small>
      </div>

      <div class="form-field">
        <label class="field-label">Descripción <span class="optional">(opcional)</span></label>
        <Textarea
          v-model="newDescription"
          placeholder="Describe el contenido de esta base de conocimiento…"
          rows="3"
          class="field-input"
          style="resize: none;"
        />
      </div>
    </div>

    <template #footer>
      <Button label="Cancelar" text severity="secondary" @click="showCreate = false" :disabled="creating" />
      <Button label="Crear colección" icon="pi pi-plus" :loading="creating" @click="submitCreate" />
    </template>
  </Dialog>
</template>

<style scoped>
.collection-manager {
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

/* Header */
.cm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cm-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--cyan-400);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* Selector */
.cm-label {
  display: block;
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: 0.35rem;
  font-weight: 500;
}

.cm-select {
  width: 100%;
}

.col-option {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.1rem 0;
}

.col-option-name {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.col-badge {
  font-size: 0.65rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  background: rgba(34, 211, 238, 0.12);
  color: var(--cyan-400);
  font-weight: 600;
  letter-spacing: 0.04em;
}

.col-option-stats {
  display: flex;
  gap: 0.75rem;
  font-size: 0.7rem;
  color: var(--text-muted);
}

.col-option-stats i {
  margin-right: 0.2rem;
  font-size: 0.65rem;
}

.placeholder {
  color: var(--text-muted);
}

/* Lista */
.cm-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 240px;
  overflow-y: auto;
  padding-right: 2px;
}

.col-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-card);
  cursor: pointer;
  transition: all 0.15s ease;
  gap: 0.5rem;
}

.col-row:hover {
  background: var(--bg-card-hover);
  border-color: rgba(34, 211, 238, 0.15);
}

.col-row.active {
  border-color: rgba(34, 211, 238, 0.35);
  background: rgba(34, 211, 238, 0.05);
}

.col-row-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.col-row-name {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-primary);
}

.col-row-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-row-icon {
  font-size: 0.7rem;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: color 0.15s;
}

.icon-active {
  color: var(--cyan-400);
}

.col-default-badge {
  font-size: 0.6rem !important;
}

.col-row-desc {
  font-size: 0.7rem;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-row-stats {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.1rem;
}

.stat-chip {
  font-size: 0.68rem;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.2rem;
}

.stat-chip.vectors {
  color: var(--violet-400);
}

.stat-chip i {
  font-size: 0.6rem;
}

.col-delete-btn {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;
}

.col-row:hover .col-delete-btn {
  opacity: 1;
}

/* Empty */
.cm-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 1rem;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.cm-empty i {
  font-size: 1.5rem;
  opacity: 0.4;
}

/* Refresh */
.cm-refresh {
  align-self: flex-end;
  font-size: 0.75rem;
}

/* Diálogo */
.create-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 0.5rem 0;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field-label {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.required {
  color: var(--error);
  margin-left: 0.1rem;
}

.optional {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-weight: 400;
  margin-left: 0.25rem;
}

.field-input {
  width: 100%;
}

.field-hint {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.field-error {
  font-size: 0.7rem;
  color: var(--error);
}
</style>
