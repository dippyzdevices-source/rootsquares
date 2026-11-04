import { supabase } from './supabaseClient'

export interface TicketTypeSummary {
  id: number
  name: string
  description: string | null
  price: number
  capacity: number | null
  remaining: number | null
  sale_start: string | null
  sale_end: string | null
  valid_on: string | null
  members_only: boolean
  age_category: 'adult' | 'child' | 'other'
  coupon_eligible: boolean
  status: 'upcoming' | 'on_sale' | 'ended' | 'sold_out'
}

export interface TicketTypeListResponse {
  items: TicketTypeSummary[]
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

// Public/unauthenticated endpoint — this header is only attached when a session already
// exists, purely so the backend can also include ticket types for a draft event when the
// request is an admin's own (see app.tickets.routes._optional_admin_user). A missing session,
// an expired token, or a non-admin role all behave exactly like an anonymous visitor.
async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchTicketTypes(eventId: number): Promise<TicketTypeListResponse> {
  const search = new URLSearchParams({ event_id: String(eventId) })
  const response = await fetch(`${API_BASE_URL}/api/tickets/types?${search.toString()}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch ticket types: ${response.status}`)
  }
  return response.json() as Promise<TicketTypeListResponse>
}
