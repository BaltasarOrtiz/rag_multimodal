<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import ConfirmDialog from 'primevue/confirmdialog'
import QueryPanel from '@/components/QueryPanel.vue'
import AppHeader from '@/components/AppHeader.vue'
import ConversationSidebar from '@/components/ConversationSidebar.vue'
import RightSidebar from '@/components/RightSidebar.vue'

const sidebarCollapsed = ref(false)
const isMobile = ref(false)

function syncViewport() {
  const mobile = window.innerWidth < 768
  isMobile.value = mobile
  if (mobile) {
    sidebarCollapsed.value = true
  }
}

onMounted(() => {
  syncViewport()
  window.addEventListener('resize', syncViewport)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncViewport)
})
</script>

<template>
  <div class="min-h-screen flex flex-col bg-[#0a0a0a]">
    <ConfirmDialog />
    <AppHeader />

    <main class="flex-1 min-h-0 overflow-hidden flex">
      <!-- Sidebar izquierdo: historial de conversaciones -->
      <ConversationSidebar v-model:collapsed="sidebarCollapsed" />

      <button
        v-if="isMobile && !sidebarCollapsed"
        class="fixed inset-0 top-16 z-[150] bg-black/45 border-none"
        aria-label="Cerrar panel de conversaciones"
        @click="sidebarCollapsed = true"
      />

      <!-- Columna central: chat -->
      <section class="flex-1 min-w-0 overflow-hidden flex flex-col bg-[#111111]">
        <QueryPanel class="h-full" />
      </section>

      <!-- Sidebar derecho — componente auto-contenido -->
      <RightSidebar />
    </main>
  </div>
</template>
