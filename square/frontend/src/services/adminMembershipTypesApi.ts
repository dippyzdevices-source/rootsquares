import { supabase } from './supabaseClient'

export type BillingFrequency = 'monthly' | 'quarterly' | 'yearly'

export interface AdminMembershipType {
  name: string
  price: number
  billing_frequency: BillingFrequency
  contact_for_price: boolean
  description: string | null
  is_active: boolean
  sort_order: number
}

export interface MembershipTypePayload {
  name?: string
  price?: number
  billing_frequency?: BillingFrequency
  contact_for_price?: boolean
  description?: string | null
  is_active?: boolean
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
const BASE_URL = `${API_BASE_URL}/api/admin/membership-types`

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

export async function fetchAdminMembershipTypes(): Promise<{ items: AdminMembershipType[] }> {
  const response = await fetch(BASE_URL, { headers: await authHeaders() })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<{ items: AdminMembershipType[] }>
}

export async function createAdminMembershipType(
  payload: MembershipTypePayload,
): Promise<AdminMembershipType> {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminMembershipType>
}

export async function updateAdminMembershipType(
  name: string,
  payload: MembershipTypePayload,
): Promise<AdminMembershipType> {
  const response = await fetch(`${BASE_URL}/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminMembershipType>
}
