// Tests for memberApi (14 cases), e.g. fetchMyMember; sends the bearer token and resolves with the profile; throws MemberNotFoundError on a 404.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import {
  fetchMyMember,
  saveMyMember,
  fetchMyMemberships,
  fetchMyTaskAssignments,
  requestMembershipRenewal,
  exportMyData,
  MemberNotFoundError,
  RenewalConflictError,
} from '../memberApi'

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

describe('fetchMyMember', () => {
  it('sends the bearer token and resolves with the profile', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({ id: 1, name: 'Priya Das', address: null, family_info: null }),
    })

    const result = await fetchMyMember()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/members/me'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    expect(result.name).toBe('Priya Das')
  })

  it('throws MemberNotFoundError on a 404', async () => {
    stubFetch({ ok: false, status: 404 })

    await expect(fetchMyMember()).rejects.toBeInstanceOf(MemberNotFoundError)
  })
})

describe('saveMyMember', () => {
  it('PUTs the payload with the bearer token', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({ id: 1, name: 'Priya Das', address: 'Oslo', family_info: null }),
    })

    await saveMyMember({ name: 'Priya Das', address: 'Oslo' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/members/me'),
      expect.objectContaining({
        method: 'PUT',
        headers: expect.objectContaining({ Authorization: 'Bearer token-123' }),
        body: JSON.stringify({ name: 'Priya Das', address: 'Oslo' }),
      }),
    )
  })
})

describe('fetchMyMemberships', () => {
  it('resolves with the items array', async () => {
    stubFetch({
      ok: true,
      json: () => ({ items: [{ id: 1, membership_type: 'individual', status: 'active', start_date: '2026-01-01', end_date: null }] }),
    })

    const result = await fetchMyMemberships()

    expect(result).toHaveLength(1)
    expect(result[0].status).toBe('active')
  })
})

describe('fetchMyTaskAssignments', () => {
  it('sends the bearer token and resolves with the items array', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({
        items: [
          {
            id: 1, category: 'food', event_id: 5, event_title: 'Durga Puja 2026',
            event_slug: 'durga-puja-2026', event_start_datetime: '2026-10-10T10:00:00Z',
            event_end_datetime: null,
          },
        ],
      }),
    })

    const result = await fetchMyTaskAssignments()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/members/me/task-assignments'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    expect(result).toHaveLength(1)
    expect(result[0].event_title).toBe('Durga Puja 2026')
  })
})

describe('requestMembershipRenewal', () => {
  it('POSTs the membership type with the bearer token', async () => {
    const fetchMock = stubFetch({
      ok: true,
      status: 201,
      json: () => ({ id: 2, membership_type: 'family', status: 'pending', start_date: '2026-09-10', end_date: null }),
    })

    const result = await requestMembershipRenewal('family')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/memberships/me'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer token-123' }),
        body: JSON.stringify({ membership_type: 'family' }),
      }),
    )
    expect(result.status).toBe('pending')
  })

  it('throws RenewalConflictError on a 409', async () => {
    stubFetch({ ok: false, status: 409 })

    await expect(requestMembershipRenewal('individual')).rejects.toBeInstanceOf(
      RenewalConflictError,
    )
  })
})

describe('exportMyData', () => {
  it('sends the bearer token and resolves with the export document', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({ account: { email: 'priya@example.com' }, profile: null, memberships: [], orders: [] }),
    })

    const result = await exportMyData()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/members/me/export'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    expect(result.account).toEqual({ email: 'priya@example.com' })
  })
})
