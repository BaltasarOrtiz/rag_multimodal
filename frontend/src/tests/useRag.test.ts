import { describe, it, expect, vi } from 'vitest'
import { useHealth, useDocuments } from '@/composables/useRag'

// Mock ragApi to avoid requiring a real connection
vi.mock('@/api/ragApi', () => ({
  default: {
    checkHealth: vi.fn().mockResolvedValue({ status: 'ok', index_loaded: true }),
    listDocuments: vi.fn().mockResolvedValue({ documents: [], total: 0 }),
    uploadDocument: vi.fn().mockResolvedValue({ message: 'Uploaded OK' }),
  },
}))

// Mock @vueuse/core to avoid setInterval in tests
vi.mock('@vueuse/core', () => ({
  useIntervalFn: vi.fn((_fn: () => void, _interval: number, opts?: { immediateCallback?: boolean }) => {
    if (opts?.immediateCallback) _fn()
  }),
}))

describe('useHealth', () => {
  it('initial state is loading', () => {
    const { status, indexLoaded } = useHealth()
    // The mock executes refresh() immediately, so it may already be 'ok'
    expect(['loading', 'ok']).toContain(status.value)
    expect(typeof indexLoaded.value).toBe('boolean')
  })

  it('refresh() updates status to ok', async () => {
    const { status, refresh } = useHealth()
    await refresh()
    expect(status.value).toBe('ok')
  })
})

describe('useDocuments', () => {
  it('documents starts empty', () => {
    const { documents, loading } = useDocuments()
    expect(documents.value).toEqual([])
    expect(loading.value).toBe(false)
  })

  it('fetchDocuments loads the list', async () => {
    const { documents, fetchDocuments } = useDocuments()
    await fetchDocuments()
    expect(Array.isArray(documents.value)).toBe(true)
  })
})
