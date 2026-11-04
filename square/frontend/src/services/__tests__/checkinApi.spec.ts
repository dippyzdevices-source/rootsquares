// Tests for checkinApi (4 cases), e.g. checkinApi; scanTicket posts the ticket code to the global scan endpoint, without; fetchCheckinSummary GETs the global summary endpoint, without an event.
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) } },
}))

import { scanTicket, fetchCheckinSummary } from '../checkinApi'

beforeEach(() => {
  vi.unstubAllGlobals()
})

describe('checkinApi', () => {
  it('scanTicket posts the ticket code to the global scan endpoint, without an event id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ result: 'valid', customer_name: 'Priya Das' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await scanTicket('abc123')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/checkin/scan'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ ticket_code: 'abc123' }),
      }),
    )
    expect(result.result).toBe('valid')
  })

  it('fetchCheckinSummary GETs the global summary endpoint, without an event id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ total_tickets: 10, checked_in_count: 3 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const summary = await fetchCheckinSummary()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/checkin/summary'),
      expect.anything(),
    )
    expect(summary).toEqual({ total_tickets: 10, checked_in_count: 3 })
  })

  it('throws when the scan request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))

    await expect(scanTicket('abc123')).rejects.toThrow('500')
  })
})
