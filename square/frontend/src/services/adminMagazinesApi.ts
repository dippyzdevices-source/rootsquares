import type { DescriptionStyle } from './settingsApi'
import { supabase } from './supabaseClient'

export interface AdminMagazine {
  id: number
  title: string
  slug: string
  issue_label: string | null
  issue_date: string | null
  description: string | null
  description_style: DescriptionStyle | null
  pdf_url: string | null
  cover_url: string | null
  published: boolean
  created_at: string
  updated_at: string
}

export interface MagazinePayload {
  title?: string
  issue_label?: string | null
  issue_date?: string | null
  description?: string | null
  description_style?: DescriptionStyle | null
  published?: boolean
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
const BASE_URL = `${API_BASE_URL}/api/admin/magazines`

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

export async function fetchAdminMagazines(): Promise<{ items: AdminMagazine[] }> {
  const response = await fetch(BASE_URL, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to fetch magazines: ${response.status}`)
  return response.json() as Promise<{ items: AdminMagazine[] }>
}

export async function fetchAdminMagazine(id: number): Promise<AdminMagazine> {
  const response = await fetch(`${BASE_URL}/${id}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to fetch magazine: ${response.status}`)
  return response.json() as Promise<AdminMagazine>
}

export async function createAdminMagazine(payload: MagazinePayload): Promise<AdminMagazine> {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminMagazine>
}

export async function updateAdminMagazine(id: number, payload: MagazinePayload): Promise<AdminMagazine> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminMagazine>
}

export async function deleteAdminMagazine(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Failed to delete magazine: ${response.status}`)
}

export async function uploadAdminMagazineCover(id: number, file: File): Promise<AdminMagazine> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${BASE_URL}/${id}/cover`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminMagazine>
}

export async function uploadAdminMagazinePdf(id: number, file: File): Promise<AdminMagazine> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${BASE_URL}/${id}/pdf`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminMagazine>
}
