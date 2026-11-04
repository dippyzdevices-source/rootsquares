// Tests for adminTicketsApi (6 cases), e.g. adminTicketsApi; fetchAdminTickets GETs the tickets list; fetchAdminTickets appends event_id, status, and q filters.
import { describe, it, expect, vi, afterEach } from 'vitest'

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) } },
}))

import { fetchAdminTickets, exportTickets } from '../adminTicketsApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('adminTicketsApi', () => {
  it('fetchAdminTickets GETs the tickets list', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminTickets()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/admin\/tickets$/),
      expect.anything(),
    )
  })

  it('fetchAdminTickets appends event_id, status, and q filters', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminTickets({ eventId: 3, status: 'used', q: 'rohan' })

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('event_id=3')
    expect(url).toContain('status=used')
    expect(url).toContain('q=rohan')
  })

  it('fetchAdminTickets appends a sort param when given', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminTickets({ sort: 'checked_in_at_desc' })

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('sort=checked_in_at_desc')
  })

  it('exportTickets GETs the export endpoint and returns a blob', async () => {
    const fakeBlob = new Blob(['data'])
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => fakeBlob })
    vi.stubGlobal('fetch', fetchMock)

    const result = await exportTickets()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/tickets/export'),
      expect.anything(),
    )
    expect(result).toBe(fakeBlob)
  })

  it('throws when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))

    await expect(fetchAdminTickets()).rejects.toThrow('500')
  })
})
