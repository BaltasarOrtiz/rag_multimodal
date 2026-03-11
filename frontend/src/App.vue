<script setup lang="ts">
import Toast from 'primevue/toast'
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="dark-mode">
    <Toast position="top-right" />
    <RouterView />
  </div>
</template>

<style>
.dark-mode {
  min-height: 100vh;
}
</style>
