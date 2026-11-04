import { supabase } from './supabaseClient'

export interface CouponValidation {
  valid: boolean
  code?: string
  discount_percent?: number
  // Empty/absent means unrestricted (applies to any coupon-eligible ticket type).
  allowed_ticket_type_ids?: number[]
  // null/absent means unlimited. Otherwise, how many more tickets this coupon can be used for
  // right now — see Coupon.max_redemptions in the backend for the full definition.
  remaining_redemptions?: number | null
  error?: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

/** Public, read-only preview — checkout itself always re-validates and re-computes the
 * discount server-side, so a failed/invalid result here is only ever a UX hint. The auth header
 * (defined below, hoisted) is only attached when a session already exists, purely so the
 * backend can also preview a coupon for a draft event when the request is an admin's own (see
 * app.coupons.routes._optional_admin_user). */
export async function validateCoupon(eventId: number, code: string): Promise<CouponValidation> {
  const search = new URLSearchParams({ event_id: String(eventId), code })
  const response = await fetch(`${API_BASE_URL}/api/coupons/validate?${search.toString()}`, {
    headers: await authHeaders(),
  })
  if (response.status === 400) {
    return { valid: false, error: 'Enter a coupon code.' }
  }
  return response.json() as Promise<CouponValidation>
}

export interface AdminCoupon {
  id: number
  event_id: number
  code: string
  discount_percent: number
  is_active: boolean
  // Ticket-type ids this coupon is restricted to — empty means unrestricted (applies to any
  // coupon-eligible ticket type on the event).
  allowed_ticket_type_ids: number[]
  // null means unlimited. Once redemption_count (paid orders using this coupon) reaches this,
  // the backend auto-flips is_active to false — see app/coupons/service.py.
  max_redemptions: number | null
  redemption_count: number
  created_by_email: string | null
  updated_by_email: string | null
}

export interface CouponPayload {
  code?: string
  discount_percent?: number
  is_active?: boolean
  allowed_ticket_type_ids?: number[]
  max_redemptions?: number | null
}

export class ValidationError extends Error {
  errors: Record<string, string>

  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'ValidationError'
    this.errors = errors
  }
}

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

export async function fetchAdminCoupons(eventId: number): Promise<{ items: AdminCoupon[] }> {
  const response = await fetch(`${API_BASE_URL}/api/admin/events/${eventId}/coupons`, {
    headers: await authHeaders(),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<{ items: AdminCoupon[] }>
}

export async function createAdminCoupon(eventId: number, payload: CouponPayload): Promise<AdminCoupon> {
  const response = await fetch(`${API_BASE_URL}/api/admin/events/${eventId}/coupons`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminCoupon>
}

export async function updateAdminCoupon(couponId: number, payload: CouponPayload): Promise<AdminCoupon> {
  const response = await fetch(`${API_BASE_URL}/api/admin/coupons/${couponId}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminCoupon>
}
