import { supabase } from './supabaseClient'
import { listParam, type FilterValue } from '../utils/filterParams'

export interface OrderTicket {
  id: number
  ticket_code: string
  status: string
  qr_code_data_url: string
  checked_in_at: string | null
  issued_at?: string | null
  checked_in_by_email: string | null
  checked_in_by_name: string | null
}

export interface OrderItem {
  id: number
  ticket_type_id: number
  ticket_type_name: string | null
  quantity: number
  unit_price: number
  subtotal: number
  tickets: OrderTicket[]
}

export interface AdminOrder {
  id: number
  order_number: string
  event_id: number
  event_title: string | null
  customer_name: string
  customer_email: string
  customer_phone: string | null
  total_amount: number
  coupon_code: string | null
  coupon_percent?: number | null
  discount_amount: number
  payment_status: string
  order_status: string
  items: OrderItem[]
  created_at: string
  updated_at?: string | null
  /** Is the buyer a member? Matched by email on the server. */
  customer_member?: {
    status: 'member' | 'former' | 'guest'
    member_id: number | null
    membership_type: string | null
    photo_url: string | null
  }
  approved_by_name: string | null
  approved_by_email: string | null
  approved_at: string | null
  rejected_by_name: string | null
  rejected_by_email: string | null
  rejected_at: string | null
  rejection_reason: string | null
  cancelled_by_name: string | null
  cancelled_by_email: string | null
  cancelled_at: string | null
  cancellation_reason: string | null
  payments?: {
    id: number
    payment_reference: string | null
    provider: string
    amount: number
    surcharge_amount: number
    processing_fee_amount: number
    status: string
    paid_at: string | null
    created_at: string
    updated_at?: string | null
  }[]
}

export interface AdminOrdersPage {
  items: AdminOrder[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface AdminOrdersFilter {
  page?: number
  perPage?: number
  eventId?: FilterValue
  paymentStatus?: FilterValue
  q?: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchAdminOrders(filter: AdminOrdersFilter = {}): Promise<AdminOrdersPage> {
  const params = new URLSearchParams()
  if (filter.page) params.set('page', String(filter.page))
  if (filter.perPage) params.set('per_page', String(filter.perPage))
  const eventIds = listParam(filter.eventId)
  if (eventIds) params.set('event_id', eventIds)
  const statuses = listParam(filter.paymentStatus)
  if (statuses) params.set('payment_status', statuses)
  if (filter.q) params.set('q', filter.q)

  const query = params.toString()
  const response = await fetch(`${API_BASE_URL}/api/admin/orders${query ? `?${query}` : ''}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<AdminOrdersPage>
}

export async function fetchAdminOrder(orderId: number): Promise<AdminOrder> {
  const response = await fetch(`${API_BASE_URL}/api/admin/orders/${orderId}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<AdminOrder>
}

/** The orders table as an .xlsx; takes the same filters as the list so the download matches what the page shows. */
export async function exportOrders(filter: Pick<AdminOrdersFilter, 'eventId' | 'paymentStatus' | 'q'> = {}): Promise<Blob> {
  const params = new URLSearchParams()
  const eventIds = listParam(filter.eventId)
  if (eventIds) params.set('event_id', eventIds)
  const statuses = listParam(filter.paymentStatus)
  if (statuses) params.set('payment_status', statuses)
  if (filter.q) params.set('q', filter.q)
  const query = params.toString()
  const response = await fetch(`${API_BASE_URL}/api/admin/orders/export${query ? `?${query}` : ''}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Failed to export orders: ${response.status}`)
  return response.blob()
}

/** `method` records how it was really paid (cash or vipps_qr); omitted = keep what the order was placed with. */
export async function markOrderPaid(orderId: number, method?: 'cash' | 'vipps_qr' | 'bank_transfer'): Promise<AdminOrder> {
  const response = await fetch(`${API_BASE_URL}/api/admin/orders/${orderId}/mark-paid`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(method ? { payment_method: method } : {}),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<AdminOrder>
}

export async function rejectOrder(orderId: number, reason: string): Promise<AdminOrder> {
  const response = await fetch(`${API_BASE_URL}/api/admin/orders/${orderId}/reject`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<AdminOrder>
}

/** Sends the tickets-confirmed email to the buyer again; resolves with the address it went to. */
export async function resendConfirmation(orderId: number): Promise<{ sent_to: string }> {
  const response = await fetch(`${API_BASE_URL}/api/admin/orders/${orderId}/resend-confirmation`, {
    method: 'POST',
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<{ sent_to: string }>
}

export async function cancelOrder(orderId: number, reason: string): Promise<AdminOrder> {
  const response = await fetch(`${API_BASE_URL}/api/admin/orders/${orderId}/cancel`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<AdminOrder>
}
