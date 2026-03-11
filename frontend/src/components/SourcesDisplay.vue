<script setup lang="ts">
import { ref } from 'vue'
import type { SourceInfo } from '@/types/rag'

defineProps<{
  sources: SourceInfo[]
}>()

const expanded = ref<Record<string, boolean>>({})

function toggle(filename: string) {
  expanded.value[filename] = !expanded.value[filename]
}
</script>

<template>
  <div v-if="sources.length" class="sources">
    <div class="sources-header">
      <i class="pi pi-book" />
      <span>Fuentes recuperadas</span>
    </div>
    <div class="sources-list">
      <div v-for="source in sources" :key="source.filename + source.score" class="source-item">
        <div class="source-chip" @click="toggle(source.filename)">
          <i class="pi pi-file" />
          <span class="source-name">{{ source.filename }}</span>
          <span class="source-score">{{ (source.score * 100).toFixed(0) }}%</span>
          <i :class="['pi', 'expand-icon', expanded[source.filename] ? 'pi-chevron-up' : 'pi-chevron-down']" />
        </div>
        <Transition name="chunk">
          <div v-if="expanded[source.filename]" class="chunk-preview">
            <p class="chunk-text">{{ source.text }}</p>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sources {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding-top: 0.875rem;
  border-top: 1px solid var(--border-subtle);
}

.sources-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.sources-header i {
  color: var(--violet-400);
}

.sources-list {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.source-item {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.source-chip {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.3rem 0.75rem;
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 9999px;
  font-size: 0.72rem;
  color: var(--violet-400);
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
  width: fit-content;
}

.source-chip:hover {
  background: rgba(139, 92, 246, 0.15);
}

.source-name {
  max-width: 14rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-score {
  background: rgba(139, 92, 246, 0.15);
  border-radius: 9999px;
  padding: 0 0.4rem;
  font-size: 0.65rem;
  opacity: 0.85;
}

.expand-icon {
  font-size: 0.6rem;
  opacity: 0.7;
  margin-left: 0.125rem;
}

.chunk-preview {
  margin-top: 0.375rem;
  padding: 0.625rem 0.875rem;
  background: rgba(139, 92, 246, 0.04);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 8px;
  overflow: hidden;
}

.chunk-text {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.6;
  color: var(--text-muted);
  white-space: pre-wrap;
  word-break: break-word;
}

/* Transition */
.chunk-enter-active,
.chunk-leave-active {
  transition: max-height 0.25s ease, opacity 0.2s ease;
  max-height: 200px;
}

.chunk-enter-from,
.chunk-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>

