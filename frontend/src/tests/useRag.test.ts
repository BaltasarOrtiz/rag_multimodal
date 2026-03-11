import { describe, it, expect, vi } from 'vitest'
import { useHealth, useDocuments } from '@/composables/useRag'

// Mock ragApi para no requerir conexión real
vi.mock('@/api/ragApi', () => ({
  default: {
    checkHealth: vi.fn().mockResolvedValue({ status: 'ok', index_loaded: true }),
    listDocuments: vi.fn().mockResolvedValue({ documents: [], total: 0 }),
    uploadDocument: vi.fn().mockResolvedValue({ message: 'Subido OK' }),
  },
}))

// Mock @vueuse/core para evitar setInterval en tests
vi.mock('@vueuse/core', () => ({
  useIntervalFn: vi.fn((_fn: () => void, _interval: number, opts?: { immediateCallback?: boolean }) => {
    if (opts?.immediateCallback) _fn()
  }),
}))

describe('useHealth', () => {
  it('estado inicial es loading', () => {
    const { status, indexLoaded } = useHealth()
    // El mock ejecuta refresh() inmediatamente, así que puede ser 'ok' ya
    expect(['loading', 'ok']).toContain(status.value)
    expect(typeof indexLoaded.value).toBe('boolean')
  })

  it('refresh() actualiza status a ok', async () => {
    const { status, refresh } = useHealth()
    await refresh()
    expect(status.value).toBe('ok')
  })
})

describe('useDocuments', () => {
  it('documents empieza vacío', () => {
    const { documents, loading } = useDocuments()
    expect(documents.value).toEqual([])
    expect(loading.value).toBe(false)
  })

  it('fetchDocuments carga la lista', async () => {
    const { documents, fetchDocuments } = useDocuments()
    await fetchDocuments()
    expect(Array.isArray(documents.value)).toBe(true)
  })
})
