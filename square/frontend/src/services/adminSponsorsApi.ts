import { supabase } from './supabaseClient'

export interface AdminSponsor {
  id: number
  name: string
  logo_url: string | null
  website_url: string | null
  display_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SponsorPayload {
  name?: string
  website_url?: string | null
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
const BASE_URL = `${API_BASE_URL}/api/admin/sponsors`

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

export async function fetchAdminSponsors(): Promise<{ items: AdminSponsor[] }> {
  const response = await fetch(BASE_URL, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to fetch sponsors: ${response.status}`)
  return response.json() as Promise<{ items: AdminSponsor[] }>
}

export async function fetchAdminSponsor(id: number): Promise<AdminSponsor> {
  const response = await fetch(`${BASE_URL}/${id}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to fetch sponsor: ${response.status}`)
  return response.json() as Promise<AdminSponsor>
}

export async function createAdminSponsor(payload: SponsorPayload): Promise<AdminSponsor> {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminSponsor>
}

export async function updateAdminSponsor(id: number, payload: SponsorPayload): Promise<AdminSponsor> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminSponsor>
}

export async function deleteAdminSponsor(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Failed to delete sponsor: ${response.status}`)
}

export async function uploadAdminSponsorLogo(id: number, file: File): Promise<AdminSponsor> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${BASE_URL}/${id}/logo`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminSponsor>
}
