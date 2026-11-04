import { supabase } from './supabaseClient'

export interface FamilyMember {
  id: number
  name: string
  relationship_type: string
  age: number | null
  sort_order: number
}

export interface FamilyMemberPayload {
  name?: string
  relationship_type?: string
  age?: number | null
  sort_order?: number
}

export interface MemberProfile {
  id: number
  name: string
  phone: string | null
  address: string | null
  photo_url: string | null
  family_info: string | null
  family_members: FamilyMember[]
}

export interface MembershipRecord {
  id: number
  membership_type: string
  status: string
  start_date: string
  end_date: string | null
}

export interface MyTaskAssignment {
  id: number
  category: string
  event_id: number
  event_title: string
  event_slug: string
  event_start_datetime: string
  event_end_datetime: string | null
}

export interface MembershipTypeOption {
  name: string
  price: number | null
  billing_frequency: 'monthly' | 'quarterly' | 'yearly'
  contact_for_price: boolean
  description?: string | null
}

export interface MemberProfilePayload {
  name: string
  phone?: string | null
  address?: string | null
  family_info?: string | null
}

export class MemberNotFoundError extends Error {
  constructor() {
    super('Member profile not created yet')
    this.name = 'MemberNotFoundError'
  }
}

export class ValidationError extends Error {
  errors: Record<string, string>

  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'ValidationError'
    this.errors = errors
  }
}

export class RenewalConflictError extends Error {
  constructor() {
    super('You already have an active or pending membership')
    this.name = 'RenewalConflictError'
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchMyMember(): Promise<MemberProfile> {
  const response = await fetch(`${API_BASE_URL}/api/members/me`, {
    headers: await authHeaders(),
  })
  if (response.status === 404) {
    throw new MemberNotFoundError()
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch member profile: ${response.status}`)
  }
  return response.json() as Promise<MemberProfile>
}

export async function saveMyMember(payload: MemberProfilePayload): Promise<MemberProfile> {
  const response = await fetch(`${API_BASE_URL}/api/members/me`, {
    method: 'PUT',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`Failed to save member profile: ${response.status}`)
  }
  return response.json() as Promise<MemberProfile>
}

export async function uploadMyPhoto(file: File): Promise<MemberProfile> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/api/members/me/photo`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) {
    throw new Error(`Failed to upload photo: ${response.status}`)
  }
  return response.json() as Promise<MemberProfile>
}

async function throwForFamilyErrorResponse(response: Response): Promise<never> {
  if (response.status === 400) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    if (body.errors) {
      throw new ValidationError(body.errors)
    }
  }
  throw new Error(`Request failed: ${response.status}`)
}

export async function createMyFamilyMember(payload: FamilyMemberPayload): Promise<FamilyMember> {
  const response = await fetch(`${API_BASE_URL}/api/members/me/family`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForFamilyErrorResponse(response)
  return response.json() as Promise<FamilyMember>
}

export async function updateMyFamilyMember(
  id: number,
  payload: FamilyMemberPayload,
): Promise<FamilyMember> {
  const response = await fetch(`${API_BASE_URL}/api/members/me/family/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForFamilyErrorResponse(response)
  return response.json() as Promise<FamilyMember>
}

export async function deleteMyFamilyMember(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/members/me/family/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to delete family member: ${response.status}`)
  }
}

export async function fetchMyMemberships(): Promise<MembershipRecord[]> {
  const response = await fetch(`${API_BASE_URL}/api/memberships/me`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch memberships: ${response.status}`)
  }
  const data = (await response.json()) as { items: MembershipRecord[] }
  return data.items
}

export async function fetchMyTaskAssignments(): Promise<MyTaskAssignment[]> {
  const response = await fetch(`${API_BASE_URL}/api/members/me/task-assignments`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch volunteering assignments: ${response.status}`)
  }
  const data = (await response.json()) as { items: MyTaskAssignment[] }
  return data.items
}

export async function fetchMembershipTypes(): Promise<MembershipTypeOption[]> {
  // Public — no auth header needed. Powers both the marketing /membership page and this
  // dashboard's renewal dropdown, so a rate change only ever needs an admin edit, not a deploy.
  const response = await fetch(`${API_BASE_URL}/api/memberships/types`)
  if (!response.ok) {
    throw new Error(`Failed to fetch membership types: ${response.status}`)
  }
  const data = (await response.json()) as { items: MembershipTypeOption[] }
  return data.items
}

export async function exportMyData(): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/api/members/me/export`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to export your data: ${response.status}`)
  }
  return response.json() as Promise<Record<string, unknown>>
}

/** The member changes their mind before paying: removes their own unpaid pending request. */
export async function cancelMyMembershipRequest(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/memberships/me/request`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string }
    throw new Error(body.error ?? 'Could not cancel your request')
  }
}

export async function requestMembershipRenewal(
  membershipType: string,
): Promise<MembershipRecord> {
  const response = await fetch(`${API_BASE_URL}/api/memberships/me`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ membership_type: membershipType }),
  })
  if (response.status === 409) {
    throw new RenewalConflictError()
  }
  if (!response.ok) {
    throw new Error(`Failed to request membership renewal: ${response.status}`)
  }
  return response.json() as Promise<MembershipRecord>
}
