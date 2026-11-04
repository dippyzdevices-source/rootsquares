// Tests for adminImportsApi (6 cases), e.g. previewMembersImport; POSTs the file as multipart form data with the bearer token; confirmMembersImport.
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import { previewMembersImport, confirmMembersImport, fetchImportHistory } from '../adminImportsApi'

beforeEach(() => {
  vi.clearAllMocks()
  mockGetSession.mockResolvedValue({ data: { session: { access_token: 'token-123' } } })
})

describe('previewMembersImport', () => {
  it('POSTs the file as multipart form data with the bearer token', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ rows: [], valid_count: 0, invalid_count: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const file = new File(['data'], 'members.xlsx')
    await previewMembersImport(file)

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/admin/imports/members/preview')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ Authorization: 'Bearer token-123' })
    expect(init.body).toBeInstanceOf(FormData)
    vi.unstubAllGlobals()
  })
})

describe('confirmMembersImport', () => {
  it('POSTs the filename and rows as JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: 1, filename: 'members.xlsx', total_rows: 1, members_created: 1, memberships_created: 1, failed_rows: 0, admin_email: 'admin@example.com', created_at: '2026-09-10T10:00:00Z' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await confirmMembersImport('members.xlsx', [{ name: 'Priya Das', email: 'priya@example.com' }])

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/imports/members/confirm'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ filename: 'members.xlsx', rows: [{ name: 'Priya Das', email: 'priya@example.com' }] }),
      }),
    )
    vi.unstubAllGlobals()
  })
})

describe('fetchImportHistory', () => {
  it('fetches a page of import history with the bearer token', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchImportHistory()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/imports'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    vi.unstubAllGlobals()
  })
})
