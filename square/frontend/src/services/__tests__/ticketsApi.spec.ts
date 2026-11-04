// Tests for ticketsApi (4 cases), e.g. fetchTicketTypes; requests ticket types for the given event; resolves with the parsed response.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { fetchTicketTypes } from '../ticketsApi'

function stubFetch(response: { ok: boolean; status?: number; json?: () => unknown }) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchTicketTypes', () => {
  it('requests ticket types for the given event', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [] }) })

    await fetchTicketTypes(1)

    expect(fetchMock.mock.calls[0][0]).toContain('event_id=1')
  })

  it('resolves with the parsed response', async () => {
    const body = { items: [{ id: 1, name: 'Adult', status: 'on_sale' }] }
    stubFetch({ ok: true, json: () => body })

    const result = await fetchTicketTypes(1)

    expect(result).toEqual(body)
  })

  it('throws when the response is not ok', async () => {
    stubFetch({ ok: false, status: 500 })

    await expect(fetchTicketTypes(1)).rejects.toThrow('Failed to fetch ticket types: 500')
  })
})
