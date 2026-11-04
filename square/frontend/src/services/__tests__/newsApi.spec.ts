// Tests for newsApi (9 cases), e.g. fetchNews; requests the news list and resolves with the parsed response; throws when the response is not ok.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { fetchNews, fetchNewsArticle, NewsNotFoundError } from '../newsApi'

function stubFetch(response: { ok: boolean; status?: number; json?: () => unknown }) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchNews', () => {
  it('requests the news list and resolves with the parsed response', async () => {
    const body = { items: [{ id: 1, title: 'Renewal' }], page: 1, per_page: 10, total: 1, total_pages: 1 }
    const fetchMock = stubFetch({ ok: true, json: () => body })

    const result = await fetchNews()

    expect(fetchMock.mock.calls[0][0]).toContain('/api/news')
    expect(result).toEqual(body)
  })

  it('throws when the response is not ok', async () => {
    stubFetch({ ok: false, status: 500 })

    await expect(fetchNews()).rejects.toThrow('Failed to fetch news: 500')
  })

  it('includes the category filter in the query string when given', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [] }) })

    await fetchNews({ category: 'story' })

    expect(fetchMock.mock.calls[0][0]).toContain('category=story')
  })

  it('omits the category filter when not given', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [] }) })

    await fetchNews()

    expect(fetchMock.mock.calls[0][0]).not.toContain('category')
  })
})

describe('fetchNewsArticle', () => {
  it('requests the article by slug', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ slug: 'renewal' }) })

    await fetchNewsArticle('renewal')

    expect(fetchMock.mock.calls[0][0]).toContain('/api/news/renewal')
  })

  it('throws NewsNotFoundError on a 404', async () => {
    stubFetch({ ok: false, status: 404 })

    await expect(fetchNewsArticle('missing')).rejects.toBeInstanceOf(NewsNotFoundError)
  })

  it('throws a generic error on other failures', async () => {
    stubFetch({ ok: false, status: 500 })

    await expect(fetchNewsArticle('renewal')).rejects.toThrow('Failed to fetch article: 500')
  })
})
