// Tests for galleryApi (7 cases), e.g. fetchAlbums; requests the albums list and resolves with the parsed response; throws when the response is not ok.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { fetchAlbums, fetchAlbum } from '../galleryApi'

function stubFetch(response: { ok: boolean; status?: number; json?: () => unknown }) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchAlbums', () => {
  it('requests the albums list and resolves with the parsed response', async () => {
    const body = { items: [{ id: 1, title: 'Durga Puja' }], page: 1, per_page: 20, total: 1, total_pages: 1 }
    const fetchMock = stubFetch({ ok: true, json: () => body })

    const result = await fetchAlbums()

    expect(fetchMock.mock.calls[0][0]).toContain('/api/gallery/albums')
    expect(result).toEqual(body)
  })

  it('throws when the response is not ok', async () => {
    stubFetch({ ok: false, status: 500 })

    await expect(fetchAlbums()).rejects.toThrow('Failed to fetch albums: 500')
  })

  it('includes an event_id filter when given', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }) })

    await fetchAlbums(1, 20, 42)

    expect(fetchMock.mock.calls[0][0]).toContain('event_id=42')
  })
})

describe('fetchAlbum', () => {
  it('requests the album by id', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ id: 1, title: 'Durga Puja', media: [] }) })

    await fetchAlbum(1)

    expect(fetchMock.mock.calls[0][0]).toContain('/api/gallery/albums/1')
  })

  it('throws when the album is not found', async () => {
    stubFetch({ ok: false, status: 404 })

    await expect(fetchAlbum(1)).rejects.toThrow('Failed to fetch album: 404')
  })
})
