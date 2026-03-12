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
  <header class="sticky top-0 z-[100] bg-cape-cod-950/85 backdrop-blur-md border-b border-white/10">
    <div class="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between">
      <!-- Logo -->
      <div class="flex items-center gap-3.5">
        <div class="w-10 h-10 bg-gradient-to-br from-cape-cod-500 to-cape-cod-700 rounded-xl flex items-center justify-center text-lg text-white shadow-[0_0_20px_rgba(81,89,92,0.3)]">
          <i class="pi pi-database" />
        </div>
        <div class="flex flex-col leading-tight">
          <span class="text-lg font-bold gradient-text">RAG Multimodal</span>
          <span class="text-[0.6875rem] text-cape-cod-500 tracking-wider uppercase">LlamaIndex · Gemini · Qdrant</span>
        </div>
      </div>

      <!-- Centro: selector de colección activa -->
      <Select
        :model-value="collectionStore.activeCollection"
        :options="collectionOptions"
        option-label="label"
        option-value="value"
        placeholder="Colección..."
        class="hidden sm:block min-w-[160px] max-w-[220px] text-sm !bg-white/5 !border-white/10 !text-cape-cod-50 hover:!border-cape-cod-400/40 rounded-lg px-2 py-1"
        :disabled="!collectionOptions.length"
        @change="onCollectionChange($event.value)"
      >
        <template #value="slotProps">
            <span v-if="slotProps.value" class="text-cape-cod-400 font-medium">{{ collectionOptions.find(o => o.value === slotProps.value)?.label }}</span>
            <span v-else class="text-cape-cod-500">Colección...</span>
        </template>
        <template #option="slotProps">
             <div :class="{'text-cape-cod-400 bg-cape-cod-400/10': slotProps.option.value === collectionStore.activeCollection}">{{slotProps.option.label}}</div>
        </template>
      </Select>

      <!-- Acciones del header -->
      <div class="flex items-center gap-4">
        <!-- Botón de configuraciones -->
        <Button
          icon="pi pi-cog"
          text
          rounded
          class="!text-cape-cod-500 hover:!text-cape-cod-400 shrink-0"
          title="Configuraciones"
          @click="router.push('/settings')"
        />

        <!-- Status badge -->
        <div 
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-full text-[0.8125rem] font-medium border border-white/10 bg-white/5 transition-all duration-300"
          :class="{
            'border-amber-500/30 bg-amber-500/10 text-amber-500': status === 'loading',
            'border-emerald-500/30 bg-emerald-500/10 text-emerald-500': status === 'ok',
            'border-red-500/30 bg-red-500/10 text-red-500': status === 'error'
          }"
        >
          <span 
            class="w-2 h-2 rounded-full"
            :class="{
              'bg-amber-500 animate-pulse': status === 'loading',
              'bg-emerald-500 shadow-[0_0_8px_#10b981]': status === 'ok',
              'bg-red-500': status === 'error'
            }"
          />
          <span v-if="status === 'loading'">Conectando…</span>
          <span v-else-if="status === 'ok'">
            API OK <span class="text-cape-cod-500">·</span> Index {{ indexLoaded ? 'cargado' : 'vacío' }}
          </span>
          <span v-else>API sin conexión</span>
        </div>
      </div>
    </div>
  </header>
</template>

