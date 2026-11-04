import { supabase } from './supabaseClient'
import { listParam, type FilterValue } from '../utils/filterParams'

export interface AuditLogEntry {
  id: number
  actor_email: string | null
  actor_name: string | null
  action: string
  target_type: string | null
  target_id: number | null
  description: string
  created_at: string
}

export interface AuditLogPage {
  items: AuditLogEntry[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface AuditLogFilter {
  page?: number
  perPage?: number
  action?: FilterValue
  q?: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/audit-log`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchAuditLog(filter: AuditLogFilter = {}): Promise<AuditLogPage> {
  const params = new URLSearchParams()
  if (filter.page) params.set('page', String(filter.page))
  if (filter.perPage) params.set('per_page', String(filter.perPage))
  if (listParam(filter.action)) params.set('action', listParam(filter.action)!)
  if (filter.q) params.set('q', filter.q)

  const query = params.toString()
  const response = await fetch(`${BASE_URL}${query ? `?${query}` : ''}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<AuditLogPage>
}

// Excel download of every entry matching the current search/action filter (not just the visible page).
export async function exportAuditLog(filter: Pick<AuditLogFilter, 'action' | 'q'> = {}): Promise<Blob> {
  const params = new URLSearchParams()
  if (listParam(filter.action)) params.set('action', listParam(filter.action)!)
  if (filter.q) params.set('q', filter.q)
  const query = params.toString()
  const response = await fetch(`${BASE_URL}/export${query ? `?${query}` : ''}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to export the audit log: ${response.status}`)
  }
  return response.blob()
}
