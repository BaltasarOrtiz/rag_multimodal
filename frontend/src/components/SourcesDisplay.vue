<script setup lang="ts">
import { ref } from 'vue'
import type { SourceInfo } from '@/types/rag'

type ExtendedSource = SourceInfo & { file_type?: string; multimodal_native?: boolean }

defineProps<{
  sources: ExtendedSource[]
}>()

const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.webp', '.gif'])

function isImage(src: ExtendedSource): boolean {
  return (
    IMAGE_EXTS.has((src.file_type ?? '').toLowerCase()) ||
    IMAGE_EXTS.has('.' + src.filename.split('.').pop()?.toLowerCase())
  )
}

function isNativeImage(src: ExtendedSource): boolean {
  return isImage(src) && !!src.multimodal_native
}

const expanded = ref<Record<string, boolean>>({})
const imageErrors = ref<Record<string, boolean>>({})
const imageSizes = ref<Record<string, { w: number; h: number }>>({})

function toggle(filename: string) {
  expanded.value[filename] = !expanded.value[filename]
}

function handleImageError(filename: string) {
  imageErrors.value[filename] = true
}

function handleImageLoad(filename: string, e: Event) {
  const img = e.target as HTMLImageElement
  imageSizes.value[filename] = { w: img.naturalWidth, h: img.naturalHeight }
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
          <i :class="['pi', isImage(source) ? 'pi-image' : 'pi-file']" />
          <span class="source-name">{{ source.filename }}</span>
          <span class="source-score">{{ (source.score * 100).toFixed(0) }}%</span>
          <i
            v-if="!isNativeImage(source)"
            :class="['pi', 'expand-icon', expanded[source.filename] ? 'pi-chevron-up' : 'pi-chevron-down']"
          />
        </div>
        <Transition name="chunk">
          <div v-if="expanded[source.filename] || isNativeImage(source)" class="chunk-preview">
            <template v-if="isImage(source)">
              <img
                v-if="!imageErrors[source.filename]"
                :src="`/api/files/${source.filename}`"
                :alt="source.filename"
                class="source-thumbnail"
                @error="handleImageError(source.filename)"
                @load="handleImageLoad(source.filename, $event)"
              />
              <div v-else class="image-placeholder">
                <i class="pi pi-image" />
                <span>{{ source.filename }}</span>
              </div>
              <span class="native-badge">IMAGEN NATIVA</span>
              <span v-if="imageSizes[source.filename]" class="image-dims">
                {{ imageSizes[source.filename]?.w }} × {{ imageSizes[source.filename]?.h }}px
              </span>
            </template>
            <p v-else class="chunk-text">{{ source.text }}</p>
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
  color: var(--text-secondary);
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
  background: rgba(160, 168, 171, 0.08);
  border: 1px solid rgba(160, 168, 171, 0.2);
  border-radius: 9999px;
  font-size: 0.72rem;
  color: var(--text-secondary);
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
  width: fit-content;
}

.source-chip:hover {
  background: rgba(160, 168, 171, 0.14);
}

.source-name {
  max-width: 14rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-score {
  background: rgba(160, 168, 171, 0.15);
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
  background: rgba(160, 168, 171, 0.04);
  border: 1px solid rgba(160, 168, 171, 0.12);
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

/* Image preview */
.source-thumbnail {
  display: block;
  max-height: 120px;
  width: auto;
  border-radius: 6px;
  object-fit: contain;
  margin-bottom: 0.5rem;
}

.image-placeholder {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgba(160, 168, 171, 0.06);
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 0.8rem;
  margin-bottom: 0.5rem;
}

.image-placeholder i {
  font-size: 1.5rem;
  color: var(--text-secondary);
}

.native-badge {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  background: rgba(160, 168, 171, 0.1);
  border: 1px solid rgba(160, 168, 171, 0.25);
  border-radius: 9999px;
  padding: 0.125rem 0.5rem;
}

.image-dims {
  display: block;
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}
</style>

