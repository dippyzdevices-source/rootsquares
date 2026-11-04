// An Event pass in its archive (W11, ADR 044): the public site is one page, only sign-in and the owner's admin area stay reachable.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockGetSession = vi.fn()
const mockOnAuthStateChange = vi.fn()

vi.mock('../../services/supabaseClient', () => ({
  supabase: { auth: { getSession: (...a: unknown[]) => mockGetSession(...a), onAuthStateChange: (...a: unknown[]) => mockOnAuthStateChange(...a) } },
}))
vi.mock('../../services/settingsApi', () => ({
  fetchSettings: vi.fn().mockResolvedValue({ contact_email: '', contact_phone: '', contact_address: '', maintenance_mode: false, maintenance_allowed_paths: [], maintenance_hidden_paths: [] }),
}))
vi.mock('../../services/squareConfig', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/squareConfig')>()
  return { ...actual, squareProfile: { ...actual.squareProfile, eventPass: { phase: 'archive', liveUntil: '2026-11-01T00:00:00Z', archiveUntil: '2026-12-16T00:00:00Z' } } }
})

import { router } from '../index'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  mockGetSession.mockResolvedValue({ data: { session: null } })
  mockOnAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } })
})

describe('router in the archive of an Event pass', () => {
  it.each(['/', '/events', '/events/summer-fest', '/orders/lookup', '/membership', '/contact', '/member'])('sends the public address %s to the event-over page', async (path) => {
    await router.push(path)
    expect(router.currentRoute.value.path).toBe('/event-over')
  })

  it('keeps the event-over page and sign-in reachable', async () => {
    await router.push('/event-over')
    expect(router.currentRoute.value.path).toBe('/event-over')
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('does not send the admin area away (the sign-in guard of the admin area decides)', async () => {
    await router.push('/admin/event-pass')
    expect(router.currentRoute.value.path).not.toBe('/event-over')
  })
})
