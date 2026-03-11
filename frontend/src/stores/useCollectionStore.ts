import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import ragApi from '@/api/ragApi'
import type { CollectionInfo } from '@/types/rag'

/**
 * Store global para la colección activa y listado de colecciones.
 * Todos los composables y componentes deben leer la colección activa desde aquí.
 */
export const useCollectionStore = defineStore('collections', () => {
  const collections = ref<CollectionInfo[]>([])
  const activeCollection = ref<string>('')
  const loading = ref(false)
  const error = ref<string | null>(null)

  const activeInfo = computed(() =>
    collections.value.find(c => c.name === activeCollection.value) ?? null,
  )

  const defaultCollection = computed(() =>
    collections.value.find(c => c.is_default)?.name ?? '',
  )

  async function fetchCollections() {
    loading.value = true
    error.value = null
    try {
      const res = await ragApi.listCollections()
      collections.value = res.collections
      // Si no hay colección activa seleccionada, usar la activa del servidor
      if (!activeCollection.value) {
        activeCollection.value = res.active
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Error al obtener colecciones'
    } finally {
      loading.value = false
    }
  }

  function setActive(name: string) {
    activeCollection.value = name
  }

  async function createCollection(name: string, description = '') {
    loading.value = true
    error.value = null
    try {
      await ragApi.createCollection({ name, description })
      await fetchCollections()
      activeCollection.value = name
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Error al crear colección'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteCollection(name: string) {
    loading.value = true
    error.value = null
    try {
      await ragApi.deleteCollection(name)
      // Si se eliminó la colección activa, volver a la por defecto
      if (activeCollection.value === name) {
        activeCollection.value = defaultCollection.value
      }
      await fetchCollections()
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Error al eliminar colección'
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    collections,
    activeCollection,
    activeInfo,
    defaultCollection,
    loading,
    error,
    fetchCollections,
    setActive,
    createCollection,
    deleteCollection,
  }
})
