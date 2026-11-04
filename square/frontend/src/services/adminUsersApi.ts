import { supabase } from './supabaseClient'

export interface AdminUserRecord {
  id: number
  email: string
  role: string
  member_name: string | null
}

/** One sign-in account (any role) with its roster link, for the Members -> Users tab. */
export interface SignedInUser {
  id: number
  email: string
  role: string
  auth_provider: string
  member_id: number | null
  member_name: string | null
  first_sign_in: string | null
}

export interface SignedInUsersPage {
  items: SignedInUser[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface AdminUsersPage {
  items: AdminUserRecord[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface AssignableEvent {
  id: number
  title: string
  start_datetime: string
}

export interface UserEventsResponse {
  events: AssignableEvent[]
  assigned_event_ids: number[]
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
const BASE_URL = `${API_BASE_URL}/api/admin/users`

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

export async function fetchAdminUsers(q?: string, role?: string, perPage?: number, page?: number): Promise<AdminUsersPage> {
  const params = new URLSearchParams()
  if (page) params.set('page', String(page))
  if (q) params.set('q', q)
  if (role) params.set('role', role)
  if (perPage) params.set('per_page', String(perPage))
  const query = params.toString()

  const response = await fetch(`${BASE_URL}${query ? `?${query}` : ''}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminUsersPage>
}

export async function fetchSignedInUsers(options: { q?: string; roles?: string[]; page?: number; perPage?: number } = {}): Promise<SignedInUsersPage> {
  const params = new URLSearchParams()
  if (options.page) params.set('page', String(options.page))
  if (options.perPage) params.set('per_page', String(options.perPage))
  if (options.q) params.set('q', options.q)
  if (options.roles?.length) params.set('role', options.roles.join(','))
  const query = params.toString()
  const response = await fetch(`${BASE_URL}/all${query ? `?${query}` : ''}`, { headers: await authHeaders() })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<SignedInUsersPage>
}

/** Sends the welcome email to this login again; throws when the mail service could not send it. */
export async function resendWelcomeEmail(userId: number): Promise<{ sent_to: string }> {
  const response = await fetch(`${BASE_URL}/${userId}/welcome-email`, { method: 'POST', headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<{ sent_to: string }>
}

export async function updateAdminUserRole(
  id: number,
  role: 'member' | 'volunteer',
): Promise<AdminUserRecord> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminUserRecord>
}

export async function fetchAdminUserEvents(id: number): Promise<UserEventsResponse> {
  const response = await fetch(`${BASE_URL}/${id}/events`, {
    headers: await authHeaders(),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<UserEventsResponse>
}

export async function setAdminUserEvents(
  id: number,
  eventIds: number[],
): Promise<{ assigned_event_ids: number[] }> {
  const response = await fetch(`${BASE_URL}/${id}/events`, {
    method: 'PUT',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_ids: eventIds }),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<{ assigned_event_ids: number[] }>
}
