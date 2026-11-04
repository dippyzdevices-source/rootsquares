// Tests for adminNewsApi (12 cases), e.g. fetchAdminNews; sends the bearer token; sends an optional per_page override.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import {
  fetchAdminNews,
  fetchAdminNewsArticle,
  createAdminNews,
  updateAdminNews,
  deleteAdminNews,
  ValidationError,
} from '../adminNewsApi'

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

describe('fetchAdminNews', () => {
  it('sends the bearer token', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }) })

    await fetchAdminNews()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/news'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })

  it('sends an optional per_page override', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [], page: 1, per_page: 1, total: 0, total_pages: 0 }) })

    await fetchAdminNews(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('per_page=1'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })
})

describe('fetchAdminNewsArticle', () => {
  it('requests the article by id', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ id: 1 }) })

    await fetchAdminNewsArticle(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/news/1'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })
})

describe('createAdminNews', () => {
  it('POSTs the payload with the bearer token', async () => {
    const fetchMock = stubFetch({ ok: true, status: 201, json: () => ({ id: 1, title: 'New' }) })

    await createAdminNews({ title: 'New', slug: 'new', content: 'Body' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/news'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer token-123' }),
      }),
    )
  })

  it('throws a ValidationError on a 400', async () => {
    stubFetch({ ok: false, status: 400, json: () => Promise.resolve({ errors: { title: 'This field is required.' } }) })

    await expect(createAdminNews({})).rejects.toBeInstanceOf(ValidationError)
  })
})

describe('updateAdminNews', () => {
  it('PATCHes the given article', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ id: 1, status: 'published' }) })

    await updateAdminNews(1, { status: 'published' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/news/1'),
      expect.objectContaining({ method: 'PATCH' }),
    )
  })
})

describe('deleteAdminNews', () => {
  it('DELETEs the given article with the bearer token', async () => {
    const fetchMock = stubFetch({ ok: true })

    await deleteAdminNews(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/news/1'),
      expect.objectContaining({ method: 'DELETE', headers: { Authorization: 'Bearer token-123' } }),
    )
  })
})
