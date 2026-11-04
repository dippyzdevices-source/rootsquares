// Tests for adminEventSessionsApi (7 cases), e.g. createEventSession; POSTs the payload with the bearer token; throws a ValidationError on a 400.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import { createEventSession, updateEventSession, deleteEventSession, ValidationError } from '../adminEventSessionsApi'

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

describe('createEventSession', () => {
  it('POSTs the payload with the bearer token', async () => {
    const fetchMock = stubFetch({
      ok: true,
      status: 201,
      json: () => ({ id: 1, day_label: 'Friday', time: '18:00', title: 'Cultural Programme', description: null, sort_order: 0 }),
    })

    await createEventSession(1, { day_label: 'Friday', time: '18:00', title: 'Cultural Programme' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/events/1/sessions'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer token-123' }),
      }),
    )
  })

  it('throws a ValidationError on a 400', async () => {
    stubFetch({ ok: false, status: 400, json: () => Promise.resolve({ errors: { time: 'Must be a valid time.' } }) })

    await expect(createEventSession(1, {})).rejects.toBeInstanceOf(ValidationError)
  })
})

describe('updateEventSession', () => {
  it('PATCHes the given session', async () => {
    const fetchMock = stubFetch({
      ok: true,
      json: () => ({ id: 1, day_label: 'Friday', time: '19:00', title: 'Cultural Programme', description: null, sort_order: 0 }),
    })

    const result = await updateEventSession(1, 1, { time: '19:00' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/events/1/sessions/1'),
      expect.objectContaining({ method: 'PATCH' }),
    )
    expect(result.time).toBe('19:00')
  })
})

describe('deleteEventSession', () => {
  it('DELETEs the given session with the bearer token', async () => {
    const fetchMock = stubFetch({ ok: true })

    await deleteEventSession(1, 1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/events/1/sessions/1'),
      expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: 'Bearer token-123' },
      }),
    )
  })
})
