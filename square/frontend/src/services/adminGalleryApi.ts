import type { DescriptionStyle } from './settingsApi'
import { supabase } from './supabaseClient'
import type { MediaItem } from './galleryApi'

export interface AdminAlbum {
  id: number
  title: string
  description: string | null
  description_style: DescriptionStyle | null
  event_id: number | null
  category: string | null
  year: number
  published: boolean
  created_by_email: string | null
  updated_by_email: string | null
  created_at: string
  updated_at: string
  media: MediaItem[]
}

export interface AdminAlbumListResponse {
  items: AdminAlbum[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface AlbumPayload {
  title?: string
  description?: string | null
  description_style?: DescriptionStyle | null
  event_id?: number | null
  category?: string | null
  year?: number | null
  published?: boolean
}

export interface MediaUploadResult {
  created: MediaItem[]
  errors: { filename: string; error: string }[]
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
const BASE_URL = `${API_BASE_URL}/api/admin/gallery`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function throwForErrorResponse(response: Response): Promise<never> {
  if (response.status === 400) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    if (body.errors) {
      throw new ValidationError(body.errors)
    }
  }
  throw new Error(`Request failed: ${response.status}`)
}

export async function fetchAdminAlbums(
  perPage?: number,
  page?: number,
  filter: { q?: string; published?: boolean } = {},
): Promise<AdminAlbumListResponse> {
  const search = new URLSearchParams()
  if (filter.q) search.set('q', filter.q)
  if (filter.published !== undefined) search.set('published', String(filter.published))
  if (perPage) search.set('per_page', String(perPage))
  if (page) search.set('page', String(page))
  const url = search.toString() ? `${BASE_URL}/albums?${search.toString()}` : `${BASE_URL}/albums`
  const response = await fetch(url, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch albums: ${response.status}`)
  }
  return response.json() as Promise<AdminAlbumListResponse>
}

export async function fetchAdminAlbum(id: number): Promise<AdminAlbum> {
  const response = await fetch(`${BASE_URL}/albums/${id}`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch album: ${response.status}`)
  }
  return response.json() as Promise<AdminAlbum>
}

export async function createAdminAlbum(payload: AlbumPayload): Promise<AdminAlbum> {
  const response = await fetch(`${BASE_URL}/albums`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminAlbum>
}

export async function updateAdminAlbum(id: number, payload: AlbumPayload): Promise<AdminAlbum> {
  const response = await fetch(`${BASE_URL}/albums/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminAlbum>
}

export async function deleteAdminAlbum(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/albums/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to delete album: ${response.status}`)
  }
}

export async function uploadMedia(albumId: number, files: File[]): Promise<MediaUploadResult> {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }

  const response = await fetch(`${BASE_URL}/albums/${albumId}/media`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok && response.status !== 400) {
    // The backend answers failures with {"error": "..."} (413 too-large, 500 crash); a proxy in
    // front of it may answer with something else entirely — fall back to a plain reason.
    let reason = ''
    try {
      reason = ((await response.json()) as { error?: string }).error ?? ''
    } catch {
      // body wasn't JSON
    }
    if (!reason) {
      reason = response.status === 413 ? 'The file is too large for the server.' : `Server error (${response.status}).`
    }
    throw new Error(reason)
  }
  return response.json() as Promise<MediaUploadResult>
}

export async function updateMediaCaption(id: number, caption: string | null): Promise<MediaItem> {
  const response = await fetch(`${BASE_URL}/media/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ caption }),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<MediaItem>
}

export async function deleteMedia(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/media/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to delete media: ${response.status}`)
  }
}
