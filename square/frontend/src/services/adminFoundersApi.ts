import { supabase } from './supabaseClient'

export interface AdminFounder {
  id: number
  name: string
  sub_name: string | null
  role: string
  quote: string
  portrait_url: string | null
  display_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface FounderPayload {
  name?: string
  sub_name?: string | null
  role?: string
  quote?: string
  display_order?: number
  is_active?: boolean
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
const BASE_URL = `${API_BASE_URL}/api/admin/founders`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function throwForErrorResponse(response: Response): Promise<never> {
  if (response.status === 400) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    if (body.errors) {
      throw new ValidationError(body.errors)
    }
  }
  throw new Error(`Request failed: ${response.status}`)
}

export async function fetchAdminFounders(): Promise<{ items: AdminFounder[] }> {
  const response = await fetch(BASE_URL, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to fetch founders: ${response.status}`)
  return response.json() as Promise<{ items: AdminFounder[] }>
}

export async function fetchAdminFounder(id: number): Promise<AdminFounder> {
  const response = await fetch(`${BASE_URL}/${id}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to fetch founder: ${response.status}`)
  return response.json() as Promise<AdminFounder>
}

export async function createAdminFounder(payload: FounderPayload): Promise<AdminFounder> {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminFounder>
}

export async function updateAdminFounder(id: number, payload: FounderPayload): Promise<AdminFounder> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminFounder>
}

export async function deleteAdminFounder(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Failed to delete founder: ${response.status}`)
}

export async function uploadAdminFounderPhoto(id: number, file: File): Promise<AdminFounder> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${BASE_URL}/${id}/photo`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminFounder>
}
