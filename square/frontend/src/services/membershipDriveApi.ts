import { supabase } from './supabaseClient'

export interface MembershipDriveSignupPayload {
  name: string
  email?: string
  parent_email?: string
  phone?: string
  membership_type: string
  /** How it was paid: Vipps-QR (default) or Cash (only while an admin has Cash switched on). */
  payment_method?: 'vipps_qr' | 'cash' | 'pay_later'
}

export interface MembershipDriveSignupResult {
  member: { id: number; name: string; email: string | null }
  membership: {
    id: number
    membership_type: string
    status: string
    start_date: string
    end_date: string | null
  }
  payment: { id: number; amount: number; currency: string; status: string } | null
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

export async function signupMembershipDrive(
  payload: MembershipDriveSignupPayload,
): Promise<MembershipDriveSignupResult> {
  const response = await fetch(`${API_BASE_URL}/api/admin/membership-drive/signup`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (response.status === 400) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    if (body.errors) {
      throw new ValidationError(body.errors)
    }
  }
  if (!response.ok) {
    throw new Error(`Signup failed: ${response.status}`)
  }
  return response.json() as Promise<MembershipDriveSignupResult>
}

/** What the pay step may offer (Cash only while an admin has it switched on). */
export async function fetchDriveOptions(): Promise<{ cash_enabled: boolean }> {
  const response = await fetch(`${API_BASE_URL}/api/admin/membership-drive/options`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<{ cash_enabled: boolean }>
}
