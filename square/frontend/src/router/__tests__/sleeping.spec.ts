// A sleeping square (Keep, W10-R44, W17-R24): the visitor stays at the address they typed (no redirect to /under-construction), and the router touches
// nothing of the sleeping square: no maintenance lookup and no sign-in check (each would reach its paused project and start it again).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockGetSession = vi.fn()
const mockOnAuthStateChange = vi.fn()
const mockFetchSettings = vi.fn()

vi.mock('../../services/supabaseClient', () => ({
  supabase: { auth: { getSession: (...a: unknown[]) => mockGetSession(...a), onAuthStateChange: (...a: unknown[]) => mockOnAuthStateChange(...a) } },
}))
vi.mock('../../services/settingsApi', () => ({ fetchSettings: (...a: unknown[]) => mockFetchSettings(...a) }))
vi.mock('../../services/squareConfig', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/squareConfig')>()
  return { ...actual, squareProfile: { ...actual.squareProfile, sleeping: true } }
})

import { router } from '../index'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.stubGlobal('fetch', vi.fn())
  document.title = 'untouched'
})

describe('router of a sleeping square', () => {
  it.each(['/', '/events', '/events/summer-fest', '/login', '/admin/events', '/member'])('stays at %s and asks the square for nothing', async (path) => {
    await router.push(path)
    expect(router.currentRoute.value.path).toBe(path)
    expect(mockGetSession).not.toHaveBeenCalled()
    expect(mockOnAuthStateChange).not.toHaveBeenCalled()
    expect(mockFetchSettings).not.toHaveBeenCalled()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('leaves the tab title to the back-soon page (App.vue), not to the route', async () => {
    await router.push('/events')
    expect(document.title).toBe('untouched')
  })
})
