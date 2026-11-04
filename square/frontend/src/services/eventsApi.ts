import type { BankDetails } from './donationsApi'
import { supabase } from './supabaseClient'
import type { DescriptionStyle } from './settingsApi'

export interface EventSummary {
  id: number
  title: string
  slug: string
  short_description: string | null
  /** Per-event override of the site-wide description typeface; null = site default. */
  description_style: DescriptionStyle | null
  event_type: string
  start_datetime: string
  end_datetime: string | null
  /** True once the event's ticket-sales cut-off has passed (the event itself stays live). */
  sales_closed?: boolean
  /** True while the ticket-sales start (`sales_open_at`) is still in the future. */
  sales_not_open?: boolean
  sales_open_at?: string | null
  venue: string | null
  banner_image: string | null
  // Only ever false for an admin's own authenticated request — the backend never includes a
  // draft event for anyone else, so this is always true for a public/anonymous fetch.
  published: boolean
  /** 'cancelled' for an occurrence of a repeating event that was stopped after tickets had been sold (wave 14 item 6) */
  status?: string
  /** True when the event is one of a repeating series */
  repeats?: boolean
}

export interface EventListResponse {
  items: EventSummary[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface EventSessionRecord {
  id: number
  day_label: string
  time: string
  title: string
  description: string | null
  sort_order: number
}

export interface EventBanner {
  id: number
  image_url: string
  sort_order: number
}

export interface EventDetail extends EventSummary {
  sub_name: string | null
  /** How tickets can be paid for right now (the event's setting, narrowed by whether Vipps App is on). */
  payment_methods?: ('qr' | 'app' | 'bank' | 'cash' | 'card')[]
  /** Multi-day events: ticket types under a heading per day on one page, or one day at a time in tabs. */
  ticket_layout?: 'sections' | 'tabs'
  sales_close_at?: string | null
  /** The wording for Cash payers (the event's own, else the site-wide one); empty when Cash is not offered. */
  cash_note?: string
  /** The square's account details when bank transfer is on offer for this event. */
  bank?: BankDetails | null
  facebook_url: string | null
  max_tickets_per_email: number | null
  coupon_max_adult: number | null
  coupon_max_child: number | null
  instagram_url: string | null
  description: string | null
  address: string | null
  capacity: number | null
  status: string
  banners: EventBanner[]
  sessions: EventSessionRecord[]
}

export class EventNotFoundError extends Error {
  constructor(slug: string) {
    super(`Event not found: ${slug}`)
    this.name = 'EventNotFoundError'
  }
}

export interface FetchEventsParams {
  when?: string
  type?: string
  page?: number
  perPage?: number
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

// Both endpoints below are public/unauthenticated — this header is only ever attached when a
// session already exists, and it's purely additive: the backend uses it solely to decide
// whether to also include draft (unpublished) events for an admin, never to gate the request
// itself. A missing session, an expired token, or a non-admin role all behave identically to an
// anonymous visitor.
async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchEvents(params: FetchEventsParams = {}): Promise<EventListResponse> {
  const search = new URLSearchParams()
  if (params.when) search.set('when', params.when)
  if (params.type) search.set('type', params.type)
  if (params.page) search.set('page', String(params.page))
  if (params.perPage) search.set('per_page', String(params.perPage))

  const response = await fetch(`${API_BASE_URL}/api/events?${search.toString()}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch events: ${response.status}`)
  }
  return response.json() as Promise<EventListResponse>
}

export async function fetchEvent(slug: string): Promise<EventDetail> {
  const response = await fetch(`${API_BASE_URL}/api/events/${encodeURIComponent(slug)}`, {
    headers: await authHeaders(),
  })
  if (response.status === 404) {
    throw new EventNotFoundError(slug)
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch event: ${response.status}`)
  }
  return response.json() as Promise<EventDetail>
}

export async function fetchEventQr(slug: string): Promise<{ url: string; qr: string }> {
  const response = await fetch(`${API_BASE_URL}/api/events/${encodeURIComponent(slug)}/qr`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch event QR: ${response.status}`)
  }
  return response.json() as Promise<{ url: string; qr: string }>
}
