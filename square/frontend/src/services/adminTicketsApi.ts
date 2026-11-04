import { supabase } from './supabaseClient'
import { listParam, type FilterValue } from '../utils/filterParams'

export interface AdminTicketRecord {
  id: number
  order_id: number
  ticket_code: string
  status: string
  customer_name: string
  customer_email: string
  ticket_type: string | null
  event_id: number
  event_title: string | null
  issued_at?: string | null
  checked_in_at: string | null
  checked_in_by: string | null
  checked_in_by_name: string | null
}

export interface AdminTicketsPage {
  items: AdminTicketRecord[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface AdminTicketsFilter {
  page?: number
  perPage?: number
  eventId?: FilterValue
  status?: FilterValue
  q?: string
  sort?: 'checked_in_at_desc'
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/tickets`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchAdminTickets(
  filter: AdminTicketsFilter = {},
): Promise<AdminTicketsPage> {
  const params = new URLSearchParams()
  if (filter.page) params.set('page', String(filter.page))
  if (filter.perPage) params.set('per_page', String(filter.perPage))
  const eventIds = listParam(filter.eventId)
  if (eventIds) params.set('event_id', eventIds)
  const statuses = listParam(filter.status)
  if (statuses) params.set('status', statuses)
  if (filter.q) params.set('q', filter.q)
  if (filter.sort) params.set('sort', filter.sort)

  const query = params.toString()
  const response = await fetch(`${BASE_URL}${query ? `?${query}` : ''}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<AdminTicketsPage>
}

/** The tickets table as an .xlsx; takes the same filters as the list so the download matches what the page shows. */
export async function exportTickets(filter: Pick<AdminTicketsFilter, 'eventId' | 'status' | 'q'> = {}): Promise<Blob> {
  const params = new URLSearchParams()
  const eventIds = listParam(filter.eventId)
  if (eventIds) params.set('event_id', eventIds)
  const statuses = listParam(filter.status)
  if (statuses) params.set('status', statuses)
  if (filter.q) params.set('q', filter.q)
  const query = params.toString()
  const response = await fetch(`${BASE_URL}/export${query ? `?${query}` : ''}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to export tickets: ${response.status}`)
  return response.blob()
}
