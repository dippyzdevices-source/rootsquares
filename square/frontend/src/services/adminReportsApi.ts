import { supabase } from './supabaseClient'

export interface ReportsSummary {
  revenue_total: number
  tickets_total: number
  memberships_by_status: Record<string, number>
  memberships_by_type: Record<string, number>
  /** Active memberships only, by type. */
  memberships_active_by_type?: Record<string, number>
  orders_by_status: Record<string, number>
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchReportsSummary(): Promise<ReportsSummary> {
  const response = await fetch(`${API_BASE_URL}/api/admin/reports/summary`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch reports summary: ${response.status}`)
  }
  return response.json() as Promise<ReportsSummary>
}
