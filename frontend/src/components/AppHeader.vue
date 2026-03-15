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
  <header class="sticky top-0 z-[100] h-16 border-b border-white/6 bg-[#0f0f0f]">
    <div class="h-full px-4 md:px-6 flex items-center justify-between gap-4">
      <!-- Logo -->
      <div class="flex items-center gap-3.5 min-w-0">
        <div class="w-10 h-10 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center text-white shadow-lg shadow-blue-900/30 shrink-0">
          <i class="pi pi-database" />
        </div>
        <div class="flex flex-col leading-tight min-w-0">
          <span class="text-base md:text-lg font-bold text-zinc-100 truncate">RAG Multimodal</span>
          <span class="text-[0.6rem] md:text-[0.65rem] text-zinc-500 tracking-[0.18em] uppercase truncate">LlamaIndex · Gemini · Qdrant</span>
        </div>
      </div>

      <!-- Centro: selector de colección activa -->
      <Select
        :model-value="collectionStore.activeCollection"
        :options="collectionOptions"
        option-label="label"
        option-value="value"
        placeholder="Colección..."
        class="hidden lg:block w-[270px] !bg-zinc-900 !border-white/10 rounded-full"
        :disabled="!collectionOptions.length"
        @change="onCollectionChange($event.value)"
        :pt="{
          label: { class: '!text-xs !text-zinc-200' },
          dropdown: { class: '!text-zinc-500' }
        }"
      >
        <template #value="slotProps">
          <span v-if="slotProps.value" class="text-zinc-300 text-xs">Colección: <strong class="font-medium">{{ collectionOptions.find(o => o.value === slotProps.value)?.label }}</strong></span>
          <span v-else class="text-zinc-500 text-xs">Colección...</span>
        </template>
        <template #option="slotProps">
             <div :class="{'text-zinc-100 bg-zinc-700/50': slotProps.option.value === collectionStore.activeCollection, 'text-zinc-300': slotProps.option.value !== collectionStore.activeCollection}">{{slotProps.option.label}}</div>
        </template>
      </Select>

      <!-- Acciones del header -->
      <div class="flex items-center gap-2 ml-auto text-zinc-400">
        <!-- Botón de evaluación -->
        <Button
          icon="pi pi-chart-bar"
          text
          rounded
          class="!text-zinc-500 hover:!text-zinc-200 shrink-0 !w-8 !h-8"
          title="Evaluación RAG"
          @click="router.push('/eval')"
        />

        <!-- Botón de configuraciones -->
        <Button
          icon="pi pi-cog"
          text
          rounded
          class="!text-zinc-500 hover:!text-zinc-200 shrink-0 !w-8 !h-8"
          title="Configuraciones"
          @click="router.push('/settings')"
        />

        <!-- Status badge -->
        <div 
          class="hidden md:flex items-center gap-2 px-3 py-1 rounded-full text-[0.62rem] font-bold uppercase tracking-wide border"
          :class="{
            'border-amber-500/30 bg-amber-500/10 text-amber-500': status === 'loading',
            'border-emerald-500/30 bg-emerald-500/10 text-emerald-400': status === 'ok',
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
          <span v-if="status === 'loading'">API loading</span>
          <span v-else-if="status === 'ok'">
            API {{ indexLoaded ? 'online' : 'index vacío' }}
          </span>
          <span v-else>API offline</span>
        </div>
      </div>
    </div>
  </header>
</template>

