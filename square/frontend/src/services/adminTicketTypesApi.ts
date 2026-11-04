import { supabase } from './supabaseClient'

export interface AdminTicketType {
  id: number
  event_id: number
  name: string
  description: string | null
  price: number
  capacity: number | null
  sold: number
  sale_start: string | null
  sale_end: string | null
  valid_on: string | null
  members_only: boolean
  age_category: 'adult' | 'child' | 'other'
  coupon_eligible: boolean
  sort_order: number
  created_by_email: string | null
  updated_by_email: string | null
}

export interface TicketTypePayload {
  name?: string
  description?: string | null
  price?: number
  capacity?: number | null
  sale_start?: string | null
  sale_end?: string | null
  valid_on?: string | null
  members_only?: boolean
  age_category?: 'adult' | 'child' | 'other'
  coupon_eligible?: boolean
  sort_order?: number
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

export async function fetchAdminTicketTypes(
  eventId: number,
): Promise<{ items: AdminTicketType[] }> {
  const response = await fetch(`${API_BASE_URL}/api/admin/events/${eventId}/ticket-types`, {
    headers: await authHeaders(),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<{ items: AdminTicketType[] }>
}

export async function createAdminTicketType(
  eventId: number,
  payload: TicketTypePayload,
): Promise<AdminTicketType> {
  const response = await fetch(`${API_BASE_URL}/api/admin/events/${eventId}/ticket-types`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminTicketType>
}

export async function updateAdminTicketType(
  ticketTypeId: number,
  payload: TicketTypePayload,
): Promise<AdminTicketType> {
  const response = await fetch(`${API_BASE_URL}/api/admin/ticket-types/${ticketTypeId}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminTicketType>
}

export async function deleteAdminTicketType(ticketTypeId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/admin/ticket-types/${ticketTypeId}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to delete ticket type: ${response.status}`)
  }
}
