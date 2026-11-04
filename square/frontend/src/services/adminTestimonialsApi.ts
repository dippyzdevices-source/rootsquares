import { supabase } from './supabaseClient'

export type TestimonialStatus = 'pending' | 'approved' | 'rejected'

export interface AdminTestimonial {
  id: number
  quote: string
  author_name: string
  author_context: string | null
  photo_url: string | null
  sort_order: number
  is_active: boolean
  status: TestimonialStatus
  created_at: string
  updated_at: string
}

export interface AdminTestimonialListResponse {
  items: AdminTestimonial[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface TestimonialPayload {
  quote?: string
  author_name?: string
  author_context?: string | null
  photo_url?: string | null
  sort_order?: number
  is_active?: boolean
  status?: TestimonialStatus
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
const BASE_URL = `${API_BASE_URL}/api/admin/testimonials`

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

export async function fetchAdminTestimonials(
  status?: TestimonialStatus,
  perPage?: number,
  page?: number,
  q?: string,
): Promise<AdminTestimonialListResponse> {
  const search = new URLSearchParams()
  if (q) search.set('q', q)
  if (page) search.set('page', String(page))
  if (status) search.set('status', status)
  if (perPage) search.set('per_page', String(perPage))
  const query = search.toString()
  const response = await fetch(`${BASE_URL}${query ? `?${query}` : ''}`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch testimonials: ${response.status}`)
  }
  return response.json() as Promise<AdminTestimonialListResponse>
}

export async function fetchAdminTestimonial(id: number): Promise<AdminTestimonial> {
  const response = await fetch(`${BASE_URL}/${id}`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch testimonial: ${response.status}`)
  }
  return response.json() as Promise<AdminTestimonial>
}

export async function createAdminTestimonial(payload: TestimonialPayload): Promise<AdminTestimonial> {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminTestimonial>
}

export async function updateAdminTestimonial(
  id: number,
  payload: TestimonialPayload,
): Promise<AdminTestimonial> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminTestimonial>
}

export async function deleteAdminTestimonial(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to delete testimonial: ${response.status}`)
  }
}
