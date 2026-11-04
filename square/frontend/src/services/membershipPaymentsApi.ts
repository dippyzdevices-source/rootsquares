import type { BankDetails } from './donationsApi'
import { supabase } from './supabaseClient'

export interface MembershipPeriod {
  id: number
  period_start: string
  period_end: string
  label: string
  amount: number
  currency: string
  status: 'unpaid' | 'paid'
  payment_pending?: boolean
  paid_at: string | null
}

export interface MembershipTypeChange {
  from_type: string
  to_type: string
  changed_at: string
}

export interface MyPeriodsResponse {
  membership: { id: number; membership_type: string; status: string } | null
  items: MembershipPeriod[]
  vipps_app?: { enabled: boolean; surcharge_percent: number }
  /** Card payment through Stripe: on while the square has connected its own account and an admin switched it on. */
  stripe?: { enabled: boolean; surcharge_percent: number }
  /** Vipps QR: on only while an admin has switched it on AND the square has its own Vipps number. */
  vipps_qr?: { enabled: boolean; number: string | null; image_url?: string | null }
  /** Cash payment: switched on by an admin, with the wording to show. */
  cash?: { enabled: boolean; note: string }
  /** Bank transfer: on while an admin has switched it on and the square has given its account details. */
  bank?: { enabled: boolean; details: BankDetails | null }
  type_changes?: MembershipTypeChange[]
}

export interface StartPaymentResult {
  payment: {
    id: number
    payment_reference: string | null
    amount: number
    surcharge_amount?: number
    status: string
  }
  redirect_url?: string | null
}

export interface MembershipPaymentHistoryItem {
  id: number
  payment_reference: string | null
  provider: string
  amount: number
  currency: string
  status: string
  paid_at: string | null
  created_at: string
  allocations: { amount: number; label: string }[]
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/memberships/me`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export interface ChildAwaitingPayment {
  member_id: number
  name: string
  membership_type: string
  period: MembershipPeriod
}

export interface ChildrenAwaitingResponse {
  items: ChildAwaitingPayment[]
  vipps_app?: { enabled: boolean; surcharge_percent: number }
  stripe?: { enabled: boolean; surcharge_percent: number }
  cash?: { enabled: boolean; note: string }
}

/** Children of the signed-in member whose membership is waiting for its first payment. */
export async function fetchChildrenAwaitingPayment(): Promise<ChildrenAwaitingResponse> {
  const response = await fetch(`${BASE_URL}/children-awaiting`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<ChildrenAwaitingResponse>
}

export async function fetchMyPeriods(): Promise<MyPeriodsResponse> {
  const response = await fetch(`${BASE_URL}/periods`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<MyPeriodsResponse>
}

export async function startPeriodPayment(options: {
  periodIds: number[]
  provider: 'vipps_qr' | 'vipps_app' | 'stripe' | 'cash' | 'bank_transfer'
}): Promise<StartPaymentResult> {
  const response = await fetch(`${BASE_URL}/payments`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ membership_period_ids: options.periodIds, provider: options.provider }),
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<StartPaymentResult>
}

/** Asks the backend to re-check a Vipps app payment with Vipps (used when the member returns). */
export async function refreshVippsPayment(paymentId: number): Promise<{ id: number; status: string }> {
  const response = await fetch(`${BASE_URL}/payments/${paymentId}/refresh`, {
    method: 'POST',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return ((await response.json()) as { payment: { id: number; status: string } }).payment
}

export async function fetchMyMembershipPayments(): Promise<MembershipPaymentHistoryItem[]> {
  const response = await fetch(`${BASE_URL}/payments`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  const data = (await response.json()) as { items: MembershipPaymentHistoryItem[] }
  return data.items
}
