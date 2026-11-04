import { supabase } from './supabaseClient'
import type { DescriptionStyle } from './settingsApi'
import type { EventSessionRecord } from './eventsApi'
import type { TaskAssignmentRecord } from './adminEventTaskAssignmentsApi'

export interface EventBanner {
  id: number
  image_url: string
  sort_order: number
}

export interface AdminEvent {
  id: number
  title: string
  sub_name: string | null
  facebook_url: string | null
  max_tickets_per_email: number | null
  coupon_max_adult: number | null
  coupon_max_child: number | null
  instagram_url: string | null
  description_style: DescriptionStyle | null
  /** Comma-separated: qr, app, cash (the old "both" means "qr,app"). */
  ticket_payment_methods?: string
  ticket_layout?: 'sections' | 'tabs'
  cash_note?: string | null
  slug: string
  short_description: string | null
  description: string | null
  event_type: string
  start_datetime: string
  end_datetime: string | null
  sales_close_at?: string | null
  sales_closed?: boolean
  sales_open_at?: string | null
  sales_not_open?: boolean
  venue: string | null
  address: string | null
  capacity: number | null
  banner_image: string | null
  banners: EventBanner[]
  status: string
  published: boolean
  created_by_email: string | null
  updated_by_email: string | null
  created_at: string
  updated_at: string
  sessions: EventSessionRecord[]
  task_assignments: TaskAssignmentRecord[]
}

export interface AdminEventListResponse {
  items: AdminEvent[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface EventPayload {
  title?: string
  sub_name?: string | null
  facebook_url?: string | null
  max_tickets_per_email?: number | null
  coupon_max_adult?: number | null
  coupon_max_child?: number | null
  instagram_url?: string | null
  description_style?: DescriptionStyle | null
  ticket_payment_methods?: string
  ticket_layout?: 'sections' | 'tabs'
  cash_note?: string | null
  slug?: string
  short_description?: string | null
  description?: string | null
  event_type?: string
  start_datetime?: string
  end_datetime?: string | null
  sales_close_at?: string | null
  sales_open_at?: string | null
  venue?: string | null
  address?: string | null
  capacity?: number | null
  banner_image?: string | null
  status?: string
  published?: boolean
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
const BASE_URL = `${API_BASE_URL}/api/admin/events`

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

export async function fetchAdminEvents(page = 1, perPage = 20): Promise<AdminEventListResponse> {
  const search = new URLSearchParams({ page: String(page), per_page: String(perPage) })
  const response = await fetch(`${BASE_URL}?${search.toString()}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch events: ${response.status}`)
  }
  return response.json() as Promise<AdminEventListResponse>
}

export async function fetchAdminEvent(id: number): Promise<AdminEvent> {
  const response = await fetch(`${BASE_URL}/${id}`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch event: ${response.status}`)
  }
  return response.json() as Promise<AdminEvent>
}

export async function createAdminEvent(payload: EventPayload): Promise<AdminEvent> {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminEvent>
}

export async function updateAdminEvent(id: number, payload: EventPayload): Promise<AdminEvent> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminEvent>
}

export async function uploadEventBanner(id: number, file: File): Promise<AdminEvent> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${BASE_URL}/${id}/banner`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminEvent>
}

export async function deleteAdminEvent(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to delete event: ${response.status}`)
  }
}

// Appends a new banner to the event's slider — unlike uploadEventBanner (above), which
// replaces the single legacy banner_image, this never replaces an existing image.
export async function addEventBanner(id: number, file: File): Promise<AdminEvent> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${BASE_URL}/${id}/banners`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminEvent>
}

export async function deleteEventBanner(eventId: number, bannerId: number): Promise<AdminEvent> {
  const response = await fetch(`${BASE_URL}/${eventId}/banners/${bannerId}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminEvent>
}

export async function duplicateAdminEvent(id: number): Promise<AdminEvent> {
  const response = await fetch(`${BASE_URL}/${id}/duplicate`, {
    method: 'POST',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to duplicate event: ${response.status}`)
  }
  return response.json() as Promise<AdminEvent>
}
