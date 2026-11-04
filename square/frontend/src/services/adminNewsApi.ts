import type { DescriptionStyle } from './settingsApi'
import { supabase } from './supabaseClient'

export interface NewsImage {
  id: number
  image_url: string
  sort_order: number
}

export interface AdminNewsArticle {
  id: number
  title: string
  slug: string
  summary: string | null
  description_style: DescriptionStyle | null
  content: string
  banner_image: string | null
  images: NewsImage[]
  status: string
  category: string | null
  author: string | null
  published_at: string | null
  created_by_email: string | null
  updated_by_email: string | null
  created_at: string
  updated_at: string
}

export interface AdminNewsListResponse {
  items: AdminNewsArticle[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface NewsPayload {
  title?: string
  slug?: string
  summary?: string | null
  description_style?: DescriptionStyle | null
  content?: string
  banner_image?: string | null
  status?: string
  category?: string | null
  author?: string | null
  published_at?: string | null
}

export class ValidationError extends Error {
  errors: Record<string, string>

  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'ValidationError'
    this.errors = errors
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/news`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function throwForErrorResponse(response: Response): Promise<never> {
  if (response.status === 400 || response.status === 409) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    if (body.errors) {
      throw new ValidationError(body.errors)
    }
  }
  throw new Error(`Request failed: ${response.status}`)
}

export async function fetchAdminNews(
  perPage?: number,
  page?: number,
  filter: { q?: string; status?: string } = {},
): Promise<AdminNewsListResponse> {
  const search = new URLSearchParams()
  if (filter.q) search.set('q', filter.q)
  if (filter.status) search.set('status', filter.status)
  if (perPage) search.set('per_page', String(perPage))
  if (page) search.set('page', String(page))
  const url = search.toString() ? `${BASE_URL}?${search.toString()}` : BASE_URL
  const response = await fetch(url, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch news: ${response.status}`)
  }
  return response.json() as Promise<AdminNewsListResponse>
}

export async function fetchAdminNewsArticle(id: number): Promise<AdminNewsArticle> {
  const response = await fetch(`${BASE_URL}/${id}`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch article: ${response.status}`)
  }
  return response.json() as Promise<AdminNewsArticle>
}

export async function createAdminNews(payload: NewsPayload): Promise<AdminNewsArticle> {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminNewsArticle>
}

export async function updateAdminNews(id: number, payload: NewsPayload): Promise<AdminNewsArticle> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminNewsArticle>
}

export async function uploadNewsBanner(id: number, file: File): Promise<AdminNewsArticle> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${BASE_URL}/${id}/banner`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminNewsArticle>
}

// Appends a new image to the article's gallery — unlike uploadNewsBanner (above), which
// replaces the single lead banner_image, this never replaces an existing image.
export async function addNewsImage(id: number, file: File): Promise<AdminNewsArticle> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${BASE_URL}/${id}/images`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminNewsArticle>
}

export async function deleteNewsImage(newsId: number, imageId: number): Promise<AdminNewsArticle> {
  const response = await fetch(`${BASE_URL}/${newsId}/images/${imageId}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminNewsArticle>
}

export async function deleteAdminNews(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to delete article: ${response.status}`)
  }
}
