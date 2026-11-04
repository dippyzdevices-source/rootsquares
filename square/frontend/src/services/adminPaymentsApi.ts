import { supabase } from './supabaseClient'
import { listParam, type FilterValue } from '../utils/filterParams'

export interface AdminPaymentItem {
  id: number
  payment_reference: string | null
  payment_type: 'event_ticket' | 'membership' | 'vipps_test'
  payer_name: string | null
  payer_email: string | null
  order_id: number | null
  order_number?: string | null
  /** Set for membership payments: the member this payment belongs to. */
  member_id?: number | null
  provider: string
  amount: number
  currency: string
  status: string
  paid_at: string | null
  created_at: string
  updated_at?: string | null
  allocations: { amount: number; label: string }[]
  surcharge_amount?: number
  /** "vipps": refunded through Vipps by the backend; "manual": the association returns the money by hand. */
  refund_mode?: 'vipps' | 'manual'
  /** Why this paid payment cannot be refunded (event day passed, ticket already used), else null. */
  refund_blocked_reason?: string | null
}

export interface AdminPaymentsPage {
  items: AdminPaymentItem[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface AdminPaymentsFilter {
  page?: number
  perPage?: number
  payment_type?: FilterValue
  status?: FilterValue
  provider?: FilterValue
  q?: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/payments`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** The payments table as an .xlsx; takes the same filters as the list so the download matches what the page shows. */
export async function exportPayments(
  filter: Pick<AdminPaymentsFilter, 'payment_type' | 'status' | 'provider' | 'q'> = {},
): Promise<Blob> {
  const params = new URLSearchParams()
  for (const key of ['payment_type', 'status', 'provider'] as const) {
    const value = listParam(filter[key])
    if (value) params.set(key, value)
  }
  if (filter.q) params.set('q', filter.q)
  const query = params.toString()
  const response = await fetch(`${BASE_URL}/export${query ? `?${query}` : ''}`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to export payments: ${response.status}`)
  }
  return response.blob()
}

export async function fetchAdminPayments(filter: AdminPaymentsFilter = {}): Promise<AdminPaymentsPage> {
  const params = new URLSearchParams()
  if (filter.page) params.set('page', String(filter.page))
  if (filter.perPage) params.set('per_page', String(filter.perPage))
  for (const key of ['payment_type', 'status', 'provider'] as const) {
    const value = listParam(filter[key])
    if (value) params.set(key, value)
  }
  if (filter.q) params.set('q', filter.q)

  const query = params.toString()
  const response = await fetch(`${BASE_URL}${query ? `?${query}` : ''}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<AdminPaymentsPage>
}

export async function refundPayment(id: number, reason: string): Promise<AdminPaymentItem> {
  const response = await fetch(`${BASE_URL}/${id}/refund`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string }
    throw new Error(body.error ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<AdminPaymentItem>
}

export async function fetchVippsStatus(): Promise<{ configured: boolean; public: boolean }> {
  try {
    const response = await fetch(`${BASE_URL}/vipps-status`, { headers: await authHeaders() })
    if (!response.ok) return { configured: false, public: false }
    return (await response.json()) as { configured: boolean; public: boolean }
  } catch {
    return { configured: false, public: false }
  }
}

/** Admin-only 1 kr payment through the real Vipps App flow; returns where to send the admin. */
export async function startVippsTestPayment(): Promise<{ redirect_url: string }> {
  const response = await fetch(`${BASE_URL}/vipps-test`, { method: 'POST', headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<{ redirect_url: string }>
}

/** Re-checks a Vipps app payment with Vipps right now (confirms it if the customer did pay). */
export async function checkVippsPayment(id: number): Promise<AdminPaymentItem> {
  const response = await fetch(`${BASE_URL}/${id}/vipps-check`, {
    method: 'POST',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<AdminPaymentItem>
}

export async function reviewPayment(id: number, action: 'confirm' | 'reject'): Promise<AdminPaymentItem> {
  const response = await fetch(`${BASE_URL}/${id}/${action}`, {
    method: 'POST',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<AdminPaymentItem>
}
