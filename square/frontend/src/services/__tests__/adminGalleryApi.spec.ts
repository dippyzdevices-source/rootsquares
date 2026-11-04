// Tests for adminGalleryApi (16 cases), e.g. fetchAdminAlbums; sends the bearer token; sends an optional per_page override.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import {
  fetchAdminAlbums,
  fetchAdminAlbum,
  createAdminAlbum,
  updateAdminAlbum,
  deleteAdminAlbum,
  uploadMedia,
  deleteMedia,
  ValidationError,
} from '../adminGalleryApi'

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

describe('fetchAdminAlbums', () => {
  it('sends the bearer token', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }) })

    await fetchAdminAlbums()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/gallery/albums'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })

  it('sends an optional per_page override', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [], page: 1, per_page: 1, total: 0, total_pages: 0 }) })

    await fetchAdminAlbums(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('per_page=1'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })
})

describe('fetchAdminAlbum', () => {
  it('requests the album by id', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ id: 1 }) })

    await fetchAdminAlbum(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/gallery/albums/1'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })
})

describe('createAdminAlbum', () => {
  it('POSTs the payload with the bearer token', async () => {
    const fetchMock = stubFetch({ ok: true, status: 201, json: () => ({ id: 1, title: 'Mahalaya' }) })

    await createAdminAlbum({ title: 'Mahalaya' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/gallery/albums'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer token-123' }),
        body: JSON.stringify({ title: 'Mahalaya' }),
      }),
    )
  })

  it('throws a ValidationError on a 400', async () => {
    stubFetch({ ok: false, status: 400, json: () => Promise.resolve({ errors: { title: 'This field is required.' } }) })

    await expect(createAdminAlbum({})).rejects.toBeInstanceOf(ValidationError)
  })
})

describe('updateAdminAlbum', () => {
  it('PATCHes the given album', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ id: 1, published: true }) })

    await updateAdminAlbum(1, { published: true })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/gallery/albums/1'),
      expect.objectContaining({ method: 'PATCH' }),
    )
  })
})

describe('deleteAdminAlbum', () => {
  it('DELETEs the given album with the bearer token', async () => {
    const fetchMock = stubFetch({ ok: true })

    await deleteAdminAlbum(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/gallery/albums/1'),
      expect.objectContaining({ method: 'DELETE', headers: { Authorization: 'Bearer token-123' } }),
    )
  })
})

describe('uploadMedia', () => {
  it('POSTs a FormData body with the bearer token and no Content-Type override', async () => {
    const fetchMock = stubFetch({
      ok: true,
      status: 201,
      json: () => ({ created: [{ id: 1 }], errors: [] }),
    })
    const file = new File(['data'], 'photo.jpg', { type: 'image/jpeg' })

    await uploadMedia(1, [file])

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/admin/gallery/albums/1/media')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ Authorization: 'Bearer token-123' })
    expect(init.body).toBeInstanceOf(FormData)
  })
})

describe('deleteMedia', () => {
  it('DELETEs the given media item with the bearer token', async () => {
    const fetchMock = stubFetch({ ok: true })

    await deleteMedia(5)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/gallery/media/5'),
      expect.objectContaining({ method: 'DELETE', headers: { Authorization: 'Bearer token-123' } }),
    )
  })
})
