import { supabase } from './supabaseClient'

export interface LookupItem {
  value: string
  label: string
}

export interface AdminLookupValue extends LookupItem {
  id: number
  list_key: string
  sort_order: number
  is_active: boolean
  usage_count: number
  protected?: boolean
}

export interface LookupListInfo {
  key: string
  title: string
  description: string
  group?: string
  value_count?: number
  fixed?: boolean
}

export class LookupValidationError extends Error {
  errors: Record<string, string>
  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'LookupValidationError'
    this.errors = errors
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function failure(response: Response): Promise<never> {
  if (response.status === 400) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    if (body.errors) throw new LookupValidationError(body.errors)
  }
  throw new Error(`Request failed: ${response.status}`)
}

/** Active values of a list, in display order (public, no auth). */
export async function fetchLookup(listKey: string): Promise<LookupItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/lookups/${listKey}`)
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return ((await response.json()) as { items: LookupItem[] }).items
}

export async function fetchLookupLists(): Promise<LookupListInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/admin/lookups`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return ((await response.json()) as { items: LookupListInfo[] }).items
}

export async function fetchAdminLookup(listKey: string): Promise<AdminLookupValue[]> {
  const response = await fetch(`${API_BASE_URL}/api/admin/lookups/${listKey}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return ((await response.json()) as { items: AdminLookupValue[] }).items
}

export async function createLookupValue(listKey: string, payload: { value: string; label: string }): Promise<AdminLookupValue> {
  const response = await fetch(`${API_BASE_URL}/api/admin/lookups/${listKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return failure(response)
  return response.json() as Promise<AdminLookupValue>
}

/** Save a whole new display order in one request (every id of the list, in the new order). */
export async function reorderLookupValues(listKey: string, ids: number[]): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/admin/lookups/${listKey}/order`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ ids }),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
}

export async function updateLookupValue(
  listKey: string,
  id: number,
  payload: Partial<Pick<AdminLookupValue, 'label' | 'sort_order' | 'is_active'>>,
): Promise<AdminLookupValue> {
  const response = await fetch(`${API_BASE_URL}/api/admin/lookups/${listKey}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return failure(response)
  return response.json() as Promise<AdminLookupValue>
}

export async function deleteLookupValue(listKey: string, id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/admin/lookups/${listKey}/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
}
