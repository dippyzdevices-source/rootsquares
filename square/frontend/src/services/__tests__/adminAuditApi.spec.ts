// Tests for adminAuditApi (6 cases), e.g. adminAuditApi; fetchAuditLog GETs the audit log endpoint; fetchAuditLog appends action and q filters.
import { describe, it, expect, vi, afterEach } from 'vitest'

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) } },
}))

import { fetchAuditLog, exportAuditLog } from '../adminAuditApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('adminAuditApi', () => {
  it('fetchAuditLog GETs the audit log endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAuditLog()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/admin\/audit-log$/),
      expect.anything(),
    )
  })

  it('fetchAuditLog appends action and q filters', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAuditLog({ action: 'event_deleted', q: 'Durga' })

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('action=event_deleted')
    expect(url).toContain('q=Durga')
  })

  it('throws when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))

    await expect(fetchAuditLog()).rejects.toThrow('500')
  })

  it('exportAuditLog GETs /export with the filters and returns the file blob', async () => {
    const blob = new Blob(['xlsx'])
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => blob })
    vi.stubGlobal('fetch', fetchMock)

    const result = await exportAuditLog({ action: 'event_deleted', q: 'Durga' })

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toMatch(/\/api\/admin\/audit-log\/export\?/)
    expect(url).toContain('action=event_deleted')
    expect(url).toContain('q=Durga')
    expect(result).toBe(blob)
  })

  it('exportAuditLog throws when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    await expect(exportAuditLog()).rejects.toThrow('500')
  })
})
