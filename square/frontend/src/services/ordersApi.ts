import type { BankDetails } from './donationsApi'
import { supabase } from './supabaseClient'

export interface OrderTicket {
  id: number
  ticket_code: string
  status: string
  qr_code_data_url: string
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

export interface Order {
  id: number
  order_number: string
  event_id: number
  event_title: string | null
  event_start_datetime: string | null
  customer_name: string
  customer_email: string
  customer_phone: string | null
  total_amount: number
  coupon_code: string | null
  /** The coupon's percentage off (null when unknown). */
  coupon_percent?: number | null
  discount_amount: number
  payment_status: string
  order_status: string
  /** How the latest payment is made: cash, vipps_qr, vipps_app (null before any payment row exists). */
  payment_method?: string | null
  /** Set for cash orders: the wording the buyer was given. */
  cash_note?: string
  /** Set for bank transfer orders: the square's account details. */
  bank?: BankDetails | null
  items: OrderItem[]
  created_at: string
}

export interface CheckoutPayload {
  event_id: number
  items: { ticket_type_id: number; quantity: number }[]
  customer_name: string
  customer_email: string
  customer_phone: string
  coupon_code?: string
  payment_method?: 'vipps_app' | 'stripe' | 'cash' | 'bank_transfer'
}

/** The checkout response; for a Vipps app payment it also carries where to send the customer. */
export interface CheckoutResult extends Order {
  redirect_url?: string
  surcharge_amount?: number
}

export interface OrderListResponse {
  items: Order[]
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

export async function checkout(payload: CheckoutPayload): Promise<CheckoutResult> {
  const response = await fetch(`${API_BASE_URL}/api/orders`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    if (response.status === 400) {
      const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
      if (body.errors) {
        throw new ValidationError(body.errors)
      }
    }
    throw new Error(`Checkout failed: ${response.status}`)
  }
  return response.json() as Promise<CheckoutResult>
}

export async function lookupOrder(orderNumber: string, email: string): Promise<Order> {
  const search = new URLSearchParams({ order_number: orderNumber, email })
  const response = await fetch(`${API_BASE_URL}/api/orders/lookup?${search.toString()}`)
  if (response.status === 404) {
    throw new Error('Order not found')
  }
  if (!response.ok) {
    throw new Error(`Failed to look up order: ${response.status}`)
  }
  return response.json() as Promise<Order>
}

export async function confirmPayment(orderNumber: string, email: string): Promise<Order> {
  const response = await fetch(`${API_BASE_URL}/api/orders/${orderNumber}/confirm-payment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  if (!response.ok) {
    throw new Error(`Failed to report payment: ${response.status}`)
  }
  return response.json() as Promise<Order>
}

export async function fetchMyOrders(): Promise<OrderListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/orders/me`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch orders: ${response.status}`)
  }
  return response.json() as Promise<OrderListResponse>
}
