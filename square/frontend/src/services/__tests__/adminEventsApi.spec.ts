// Tests for adminEventsApi (4 cases), e.g. adminEventsApi auth headers; sends the bearer token when listing events; sends the bearer token when deleting an event.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import { fetchAdminEvents, deleteAdminEvent, duplicateAdminEvent } from '../adminEventsApi'

function stubFetch(response: { ok: boolean; status?: number; json?: () => unknown }) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

beforeEach(() => {
  mockGetSession.mockResolvedValue({ data: { session: { access_token: 'token-123' } } })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

// Regression test: these requests used to omit the Authorization header entirely, so every
// call would 401 against the real backend once EPIC 5 protected /api/admin/events/* with
// require_role("admin"). Caught while building the admin members/memberships work, which
// needed the same pattern.
describe('adminEventsApi auth headers', () => {
  it('sends the bearer token when listing events', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })

    await fetchAdminEvents()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })

  it('sends the bearer token when deleting an event', async () => {
    const fetchMock = stubFetch({ ok: true })

    await deleteAdminEvent(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/events/1'),
      expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: 'Bearer token-123' },
      }),
    )
  })

  it('sends the bearer token when duplicating an event', async () => {
    const fetchMock = stubFetch({ ok: true, status: 201, json: () => ({ id: 2, slug: 'durga-puja-2026-copy' }) })

    await duplicateAdminEvent(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/events/1/duplicate'),
      expect.objectContaining({
        method: 'POST',
        headers: { Authorization: 'Bearer token-123' },
      }),
    )
  })
})
