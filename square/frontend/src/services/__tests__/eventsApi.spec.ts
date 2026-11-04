// Tests for eventsApi (10 cases), e.g. fetchEvents; builds the query string from the given params; omits params that were not provided.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { fetchEvents, fetchEvent, EventNotFoundError } from '../eventsApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubFetch(response: { ok: boolean; status?: number; json?: () => unknown }) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('fetchEvents', () => {
  it('builds the query string from the given params', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [], page: 1, per_page: 9, total: 0, total_pages: 0 }) })

    await fetchEvents({ when: 'past', type: 'festival', page: 2, perPage: 6 })

    const requestedUrl = fetchMock.mock.calls[0][0] as string
    expect(requestedUrl).toContain('when=past')
    expect(requestedUrl).toContain('type=festival')
    expect(requestedUrl).toContain('page=2')
    expect(requestedUrl).toContain('per_page=6')
  })

  it('omits params that were not provided', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [], page: 1, per_page: 9, total: 0, total_pages: 0 }) })

    await fetchEvents({})

    const requestedUrl = fetchMock.mock.calls[0][0] as string
    expect(requestedUrl).not.toContain('when=')
    expect(requestedUrl).not.toContain('type=')
  })

  it('resolves with the parsed response body on success', async () => {
    const body = { items: [{ id: 1 }], page: 1, per_page: 9, total: 1, total_pages: 1 }
    stubFetch({ ok: true, json: () => body })

    const result = await fetchEvents()

    expect(result).toEqual(body)
  })

  it('throws when the response is not ok', async () => {
    stubFetch({ ok: false, status: 500 })

    await expect(fetchEvents()).rejects.toThrow('Failed to fetch events: 500')
  })
})

describe('fetchEvent', () => {
  it('requests the event by slug', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ slug: 'durga-puja-2026' }) })

    await fetchEvent('durga-puja-2026')

    const requestedUrl = fetchMock.mock.calls[0][0] as string
    expect(requestedUrl).toContain('/api/events/durga-puja-2026')
  })

  it('resolves with the parsed event on success', async () => {
    const body = { slug: 'durga-puja-2026', title: 'Durga Puja 2026' }
    stubFetch({ ok: true, json: () => body })

    const result = await fetchEvent('durga-puja-2026')

    expect(result).toEqual(body)
  })

  it('throws EventNotFoundError on a 404', async () => {
    stubFetch({ ok: false, status: 404 })

    await expect(fetchEvent('missing-event')).rejects.toBeInstanceOf(EventNotFoundError)
  })

  it('throws a generic error on other failures', async () => {
    stubFetch({ ok: false, status: 500 })

    await expect(fetchEvent('durga-puja-2026')).rejects.toThrow('Failed to fetch event: 500')
  })
})
