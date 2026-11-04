// Tests for adminMembershipsApi (8 cases), e.g. createAdminMembership; POSTs the payload with the bearer token; throws a ValidationError on a 400 with field errors.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import {
  createAdminMembership,
  updateAdminMembership,
  fetchAdminMemberships,
  ValidationError,
} from '../adminMembershipsApi'

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

describe('createAdminMembership', () => {
  it('POSTs the payload with the bearer token', async () => {
    const fetchMock = stubFetch({
      ok: true,
      status: 201,
      json: () => ({
        id: 1,
        membership_type: 'individual',
        status: 'pending',
        start_date: '2026-01-01',
        end_date: null,
      }),
    })

    await createAdminMembership({
      member_id: 1,
      membership_type: 'individual',
      start_date: '2026-01-01',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/memberships'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer token-123' }),
      }),
    )
  })

  it('throws a ValidationError on a 400 with field errors', async () => {
    stubFetch({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ errors: { member_id: 'Must reference an existing member.' } }),
    })

    await expect(createAdminMembership({})).rejects.toBeInstanceOf(ValidationError)
  })
})

describe('updateAdminMembership', () => {
  it('PATCHes the membership status', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({
        id: 1,
        membership_type: 'individual',
        status: 'active',
        start_date: '2026-01-01',
        end_date: null,
      }),
    })

    const result = await updateAdminMembership(1, { status: 'active' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/memberships/1'),
      expect.objectContaining({ method: 'PATCH' }),
    )
    expect(result.status).toBe('active')
  })
})

describe('fetchAdminMemberships', () => {
  it('fetches a page of memberships with an auth header', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })

    await fetchAdminMemberships()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/memberships'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })

  it('passes a status filter as a query param', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })

    await fetchAdminMemberships({ status: 'pending' })

    expect(fetchMock.mock.calls[0][0]).toContain('status=pending')
  })
})
