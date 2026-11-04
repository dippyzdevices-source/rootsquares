import { supabase } from './supabaseClient'

export interface AdminCommitteeMember {
  id: number
  name: string
  sub_name: string | null
  role: string
  portrait_url: string | null
  address: string | null
  email: string | null
  phone: string | null
  member_since: number | null
  quote: string | null
  display_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AdminCommitteeListResponse {
  items: AdminCommitteeMember[]
}

export interface CommitteeMemberPayload {
  name?: string
  sub_name?: string | null
  role?: string
  address?: string | null
  email?: string | null
  phone?: string | null
  member_since?: number | null
  quote?: string | null
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
const BASE_URL = `${API_BASE_URL}/api/admin/committee`

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

export async function fetchAdminCommittee(): Promise<AdminCommitteeListResponse> {
  const response = await fetch(BASE_URL, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to fetch committee: ${response.status}`)
  return response.json() as Promise<AdminCommitteeListResponse>
}

export async function fetchAdminCommitteeMember(id: number): Promise<AdminCommitteeMember> {
  const response = await fetch(`${BASE_URL}/${id}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to fetch committee member: ${response.status}`)
  return response.json() as Promise<AdminCommitteeMember>
}

export async function createAdminCommitteeMember(
  payload: CommitteeMemberPayload,
): Promise<AdminCommitteeMember> {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminCommitteeMember>
}

export async function updateAdminCommitteeMember(
  id: number,
  payload: CommitteeMemberPayload,
): Promise<AdminCommitteeMember> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminCommitteeMember>
}

export async function deleteAdminCommitteeMember(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Failed to delete committee member: ${response.status}`)
}

export async function uploadAdminCommitteePhoto(id: number, file: File): Promise<AdminCommitteeMember> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${BASE_URL}/${id}/photo`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminCommitteeMember>
}
