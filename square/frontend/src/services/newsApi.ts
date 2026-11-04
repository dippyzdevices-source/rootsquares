import type { DescriptionStyle } from './settingsApi'
import { optionalAuthHeaders } from './optionalAuthHeaders'
export interface NewsSummary {
  id: number
  title: string
  slug: string
  summary: string | null
  description_style: DescriptionStyle | null
  banner_image: string | null
  category: string | null
  author: string | null
  read_minutes: number
  published_at: string | null
  /** false only for an admin previewing a draft/scheduled article. */
  published?: boolean
}

export interface FetchNewsParams {
  category?: string
  page?: number
  perPage?: number
}

export interface NewsListResponse {
  items: NewsSummary[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface NewsArticleImage {
  id: number
  image_url: string
  sort_order: number
}

export interface NewsArticle extends NewsSummary {
  content: string
  images: NewsArticleImage[]
}

export class NewsNotFoundError extends Error {
  constructor(slug: string) {
    super(`Article not found: ${slug}`)
    this.name = 'NewsNotFoundError'
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export async function fetchNews(params: FetchNewsParams = {}): Promise<NewsListResponse> {
  const search = new URLSearchParams({
    page: String(params.page ?? 1),
    per_page: String(params.perPage ?? 10),
  })
  if (params.category) search.set('category', params.category)
  const response = await fetch(`${API_BASE_URL}/api/news?${search.toString()}`, {
    headers: await optionalAuthHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch news: ${response.status}`)
  }
  return response.json() as Promise<NewsListResponse>
}

export async function fetchNewsArticle(slug: string): Promise<NewsArticle> {
  const response = await fetch(`${API_BASE_URL}/api/news/${encodeURIComponent(slug)}`, {
    headers: await optionalAuthHeaders(),
  })
  if (response.status === 404) {
    throw new NewsNotFoundError(slug)
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch article: ${response.status}`)
  }
  return response.json() as Promise<NewsArticle>
}
