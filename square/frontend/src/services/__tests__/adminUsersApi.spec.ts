// Tests for adminUsersApi (6 cases), e.g. adminUsersApi; fetchAdminUsers GETs the users list; fetchAdminUsers appends a q param when given a search term.
import { describe, it, expect, vi } from 'vitest'

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) } },
}))

import { fetchAdminUsers, updateAdminUserRole, ValidationError } from '../adminUsersApi'

describe('adminUsersApi', () => {
  it('fetchAdminUsers GETs the users list', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminUsers()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/admin\/users$/),
      expect.anything(),
    )
    vi.unstubAllGlobals()
  })

  it('fetchAdminUsers appends a q param when given a search term', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminUsers('rohan')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('q=rohan'),
      expect.anything(),
    )
    vi.unstubAllGlobals()
  })

  it('fetchAdminUsers appends role and per_page params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 1, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminUsers(undefined, 'volunteer', 1)

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('role=volunteer')
    expect(url).toContain('per_page=1')
    vi.unstubAllGlobals()
  })

  it('updateAdminUserRole PATCHes the role', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, email: 'a@b.com', role: 'volunteer' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await updateAdminUserRole(1, 'volunteer')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/users/1'),
      expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ role: 'volunteer' }) }),
    )
    expect(result.role).toBe('volunteer')
    vi.unstubAllGlobals()
  })

  it('throws ValidationError on a 400 with field errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ errors: { role: 'Must be one of...' } }),
      }),
    )

    await expect(updateAdminUserRole(1, 'volunteer' as never)).rejects.toBeInstanceOf(
      ValidationError,
    )
    vi.unstubAllGlobals()
  })
})
