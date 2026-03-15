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
  <div class="flex flex-col gap-3.5">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <span class="text-[0.7rem] font-semibold text-cape-cod-500 uppercase tracking-widest">Colecciones</span>
      <Button
        icon="pi pi-plus"
        size="small"
        text
        rounded
        v-tooltip.left="'Nueva colección'"
        @click="openCreate"
        class="!text-cape-cod-400 hover:!bg-white/10"
      />
    </div>

    <!-- Selector de colección activa -->
    <div>
      <label class="block text-xs text-cape-cod-400 mb-1.5 font-medium">Colección activa</label>
      <Select
        :options="store.collections"
        optionLabel="name"
        optionValue="name"
        v-model="store.activeCollection"
        placeholder="Seleccionar colección…"
        class="w-full !bg-white/5 !border-white/10 hover:!border-cape-cod-500/50"
        :loading="store.loading"
      >
        <template #option="{ option }">
          <div class="flex flex-col gap-1 py-0.5">
            <div class="flex items-center gap-1.5 text-[0.875rem] font-medium text-cape-cod-50">
              <span>{{ option.name }}</span>
              <span v-if="option.is_default" class="text-[0.65rem] px-1.5 py-0.5 rounded bg-cape-cod-400/10 text-cape-cod-400 font-semibold tracking-wide">default</span>
            </div>
            <div class="flex gap-3 text-[0.7rem] text-cape-cod-500">
              <span><i class="pi pi-file-o mr-1 text-[0.65rem]" /> {{ option.doc_count }}</span>
              <span><i class="pi pi-server mr-1 text-[0.65rem] text-cape-cod-300" /> {{ option.vector_count.toLocaleString() }}</span>
            </div>
          </div>
        </template>
        <template #value="{ value }">
          <span v-if="value" class="text-cape-cod-50 font-medium">
            <i class="pi pi-database mr-1.5 opacity-60 text-cape-cod-400" />
            {{ value }}
          </span>
          <span v-else class="text-cape-cod-500">Seleccionar…</span>
        </template>
      </Select>
    </div>

    <!-- Lista de colecciones -->
    <div class="flex flex-col gap-1.5 max-h-60 overflow-y-auto pr-0.5" v-if="store.collections.length">
      <div
        v-for="col in store.collections"
        :key="col.name"
        class="group flex items-center justify-between py-2.5 px-3 rounded-lg border border-white/10 bg-white/5 cursor-pointer transition-all duration-150 gap-2 hover:bg-white/10 hover:border-cape-cod-400/30"
        :class="{ '!border-cape-cod-400/50 bg-cape-cod-400/10': col.name === store.activeCollection }"
        @click="store.setActive(col.name)"
      >
        <div class="flex-1 min-w-0 flex flex-col gap-1">
          <div class="flex items-center gap-1.5 text-[0.8125rem] font-medium text-cape-cod-50">
            <i class="pi pi-database text-[0.7rem] shrink-0 transition-colors duration-150" :class="col.name === store.activeCollection ? 'text-cape-cod-400' : 'text-cape-cod-500'" />
            <span class="overflow-hidden text-ellipsis whitespace-nowrap" :title="col.name">{{ col.name }}</span>
            <Badge v-if="col.is_default" value="default" severity="secondary" class="!text-[0.6rem]" />
          </div>
          <div class="text-[0.7rem] text-cape-cod-500 overflow-hidden text-ellipsis whitespace-nowrap" v-if="col.description">{{ col.description }}</div>
          <div class="flex gap-2 mt-0.5">
            <span class="text-[0.68rem] text-cape-cod-400 flex items-center gap-1" v-tooltip.bottom="'Documentos'">
              <i class="pi pi-file-o text-[0.6rem]" /> {{ col.doc_count }}
            </span>
            <span class="text-[0.68rem] text-cape-cod-300 flex items-center gap-1" v-tooltip.bottom="'Vectores indexados'">
              <i class="pi pi-server text-[0.6rem]" /> {{ col.vector_count.toLocaleString() }}
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
          class="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
        />
      </div>
    </div>

    <div v-else-if="!store.loading" class="flex flex-col items-center gap-1.5 p-4 text-cape-cod-500 text-sm">
      <i class="pi pi-inbox text-2xl opacity-40" />
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
      class="self-end text-xs !text-cape-cod-400 hover:!bg-white/10"
    />
  </div>

  <!-- Diálogo crear colección -->
  <Dialog
    v-model:visible="showCreate"
    header="Nueva colección"
    modal
    :style="{ width: '28rem' }"
    :closable="!creating"
    class="!bg-cape-cod-900 border-white/10"
  >
    <div class="flex flex-col gap-5 py-2">
      <div class="flex flex-col gap-1.5">
        <label class="text-[0.8125rem] font-medium text-cape-cod-400">Nombre <span class="text-red-400 ml-0.5">*</span></label>
        <InputText
          v-model="newName"
          placeholder="ej: medicina_2024"
          class="w-full !bg-white/5 !border-white/10"
          :invalid="!!nameError"
          @input="nameError = ''"
          @keyup.enter="submitCreate"
          autofocus
        />
        <small v-if="nameError" class="text-[0.7rem] text-red-400">{{ nameError }}</small>
        <small v-else class="text-[0.7rem] text-cape-cod-500">Solo minúsculas, números, _ y -</small>
      </div>

      <div class="flex flex-col gap-1.5">
        <label class="text-[0.8125rem] font-medium text-cape-cod-400">Descripción <span class="text-[0.7rem] text-cape-cod-500 font-normal ml-1">(opcional)</span></label>
        <Textarea
          v-model="newDescription"
          placeholder="Describe el contenido de esta base de conocimiento…"
          rows="3"
          class="w-full !bg-white/5 !border-white/10 resize-none"
        />
      </div>
    </div>

    <template #footer>
      <Button label="Cancelar" text severity="secondary" @click="showCreate = false" :disabled="creating" class="hover:bg-white/10" />
      <Button label="Crear colección" icon="pi pi-plus" :loading="creating" @click="submitCreate" class="bg-gradient-to-br from-cape-cod-600 to-cape-cod-800 border-none" />
    </template>
  </Dialog>
</template>

