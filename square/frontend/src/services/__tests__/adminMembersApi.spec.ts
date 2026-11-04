// Tests for adminMembersApi (10 cases), e.g. fetchAdminMembers; sends the bearer token and an optional search query; sends an optional linked-user role filter.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import { fetchAdminMembers, fetchAdminMember, updateAdminMember, exportMembers } from '../adminMembersApi'

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

describe('fetchAdminMembers', () => {
  it('sends the bearer token and an optional search query', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })

    await fetchAdminMembers('rohan')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('q=rohan'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })

  it('sends an optional linked-user role filter', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })

    await fetchAdminMembers('', 'volunteer')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('role=volunteer'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })

  it('sends an optional per_page override', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({ items: [], page: 1, per_page: 1, total: 0, total_pages: 0 }),
    })

    await fetchAdminMembers('', '', 1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('per_page=1'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })
})

describe('fetchAdminMember', () => {
  it('resolves with the member detail', async () => {
    stubFetch({
      ok: true,
      json: () => ({
        id: 1,
        name: 'Priya Das',
        address: null,
        family_info: null,
        email: 'priya@example.com',
        phone: null,
        memberships: [],
      }),
    })

    const result = await fetchAdminMember(1)

    expect(result.email).toBe('priya@example.com')
  })
})

describe('updateAdminMember', () => {
  it('PATCHes the payload with the bearer token', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({
        id: 1,
        name: 'Priya Das',
        address: 'Oslo',
        family_info: null,
        email: 'priya@example.com',
        phone: null,
        memberships: [],
      }),
    })

    await updateAdminMember(1, { address: 'Oslo' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/members/1'),
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ Authorization: 'Bearer token-123' }),
        body: JSON.stringify({ address: 'Oslo' }),
      }),
    )
  })
})

describe('exportMembers', () => {
  it('sends the bearer token and resolves with a blob', async () => {
    const blob = new Blob(['xlsx-data'])
    const fetchMock = stubFetch({ ok: true, json: () => ({}) })
    fetchMock.mockResolvedValue({ ok: true, blob: async () => blob })

    const result = await exportMembers()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/members/export'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    expect(result).toBe(blob)
  })
})
