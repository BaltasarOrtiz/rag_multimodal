import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import ragApi from '@/api/ragApi'
import type { CollectionInfo } from '@/types/rag'

/**
 * Global store for the active collection and collection listing.
 * All composables and components should read the active collection from here.
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
      // If no active collection is selected, use the one active on the server
      if (!activeCollection.value) {
        activeCollection.value = res.active
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Error fetching collections'
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
      error.value = e?.response?.data?.detail ?? 'Error creating collection'
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
      // If the active collection was deleted, fall back to the default
      if (activeCollection.value === name) {
        activeCollection.value = defaultCollection.value
      }
      await fetchCollections()
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Error deleting collection'
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
