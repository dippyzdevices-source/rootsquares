import { ValidationError } from './membershipDriveApi'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export type JoinPaymentMethod = 'vipps_app' | 'stripe' | 'vipps_qr' | 'pay_later'

export interface JoinPayload {
  membership_type: string
  name: string
  email?: string
  parent_email?: string
  phone?: string
  payment_method: JoinPaymentMethod
}

export interface JoinResult {
  membership_type: string
  payment_method: JoinPaymentMethod
  payment: { id: number; payment_reference: string; amount: number; status: string } | null
  redirect_url: string | null
}

export interface JoinOptions {
  payment_methods: JoinPaymentMethod[]
  /** Convenience fee per method, in percent, charged on top of the price. */
  convenience_percent: Partial<Record<JoinPaymentMethod, number>>
}

/** Payment methods the public join form may offer (Pay later is always there) and their fees. */
export async function fetchJoinOptions(): Promise<JoinOptions> {
  const fallback: JoinOptions = { payment_methods: ['pay_later'], convenience_percent: {} }
  try {
    const response = await fetch(`${API_BASE_URL}/api/memberships/join/options`)
    if (!response.ok) return fallback
    return (await response.json()) as JoinOptions
  } catch {
    return fallback
  }
}

export async function joinMembership(payload: JoinPayload): Promise<JoinResult> {
  const response = await fetch(`${API_BASE_URL}/api/memberships/join`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (response.status === 400 || response.status === 409) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    if (body.errors) throw new ValidationError(body.errors)
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string }
    throw new Error(body.error ?? 'Could not complete your signup. Please try again.')
  }
  return response.json() as Promise<JoinResult>
}
