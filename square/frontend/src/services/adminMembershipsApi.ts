import { supabase } from './supabaseClient'
import type { MembershipRecord } from './memberApi'

export interface MembershipPayload {
  member_id?: number
  membership_type?: string
  status?: string
  start_date?: string
  end_date?: string | null
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
const BASE_URL = `${API_BASE_URL}/api/admin/memberships`

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

export interface AdminMembershipRecord extends MembershipRecord {
  member_id: number
  member_name: string
  member_email: string
}

export interface AdminMembershipsPage {
  items: AdminMembershipRecord[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface AdminMembershipsFilter {
  page?: number
  perPage?: number
  status?: string
  membershipType?: string
}

export async function fetchAdminMemberships(
  filter: AdminMembershipsFilter = {},
): Promise<AdminMembershipsPage> {
  const params = new URLSearchParams()
  if (filter.page) params.set('page', String(filter.page))
  if (filter.perPage) params.set('per_page', String(filter.perPage))
  if (filter.status) params.set('status', filter.status)
  if (filter.membershipType) params.set('membership_type', filter.membershipType)

  const query = params.toString()
  const response = await fetch(`${BASE_URL}${query ? `?${query}` : ''}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<AdminMembershipsPage>
}

export async function createAdminMembership(payload: MembershipPayload): Promise<MembershipRecord> {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<MembershipRecord>
}

export async function updateAdminMembership(
  id: number,
  payload: MembershipPayload,
): Promise<MembershipRecord> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<MembershipRecord>
}
