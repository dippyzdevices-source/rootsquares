import { vi } from 'vitest'
import { LOOKUP_DEFAULTS } from './test-utils/lookupDefaults'

// Every spec sees the real default lookup labels (statuses, categories, ...) without a backend.
// A spec can still override with its own vi.mock('.../services/lookupsApi').
vi.mock('./services/lookupsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./services/lookupsApi')>()
  return { ...actual, fetchLookup: async (key: string) => LOOKUP_DEFAULTS[key] ?? [] }
})
