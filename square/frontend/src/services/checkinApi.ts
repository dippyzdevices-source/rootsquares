import { supabase } from './supabaseClient'

export interface ScanResult {
  // 'error' is never returned by the backend — it's a frontend-synthesized state for
  // network/server failures (see CheckinScanView.vue's submitCode), kept distinct from a
  // genuinely invalid ticket code.
  result: 'valid' | 'already_used' | 'not_assigned' | 'invalid' | 'error' | 'pre_event' | 'post_event' | 'voided'
  customer_name?: string
  ticket_type?: string
  event_title?: string
  checked_in_at?: string
  checked_in_by?: string
  checked_in_by_name?: string
  event_start_date?: string
  event_end_date?: string
}

export interface CheckinSummary {
  total_tickets: number
  checked_in_count: number
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function scanTicket(ticketCode: string): Promise<ScanResult> {
  const response = await fetch(`${API_BASE_URL}/api/admin/checkin/scan`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket_code: ticketCode }),
  })
  if (!response.ok) {
    throw new Error(`Scan request failed: ${response.status}`)
  }
  return response.json() as Promise<ScanResult>
}

export async function fetchCheckinSummary(): Promise<CheckinSummary> {
  const response = await fetch(`${API_BASE_URL}/api/admin/checkin/summary`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch check-in summary: ${response.status}`)
  }
  return response.json() as Promise<CheckinSummary>
}
