import { supabase } from './supabaseClient'
import { listParam, type FilterValue } from '../utils/filterParams'
import type { FamilyMember, FamilyMemberPayload, MembershipRecord } from './memberApi'

export interface AdminMemberSummary {
  id: number
  name: string
  email: string
  phone: string | null
  linked?: boolean
  latest_membership: {
    id: number
    membership_type: string
    status: string
    /** A self-service request still waiting for its first payment — nothing for an admin to approve. */
    awaiting_payment?: boolean
  } | null
}

export interface AdminMemberDetail {
  id: number
  name: string
  address: string | null
  photo_url: string | null
  family_info: string | null
  family_members: FamilyMember[]
  parent: { id: number; name: string; email: string | null } | null
  children: { id: number; name: string }[]
  email: string
  phone: string | null
  memberships: MembershipRecord[]
  erase_requested_at: string | null
  erased_at: string | null
}

export interface AdminMemberListResponse {
  items: AdminMemberSummary[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface AdminMemberProfilePayload {
  name?: string
  address?: string | null
  family_info?: string | null
  parent_email?: string | null
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/members`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export class ValidationError extends Error {
  errors: Record<string, string>

  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'ValidationError'
    this.errors = errors
  }
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

export async function fetchAdminMembers(
  q = '',
  role = '',
  perPage?: number,
  status: FilterValue = '',
  page?: number,
  membershipType: FilterValue = '',
): Promise<AdminMemberListResponse> {
  const search = new URLSearchParams()
  if (page) search.set('page', String(page))
  if (q) search.set('q', q)
  if (role) search.set('role', role)
  if (perPage) search.set('per_page', String(perPage))
  if (listParam(status)) search.set('status', listParam(status)!)
  if (listParam(membershipType)) search.set('membership_type', listParam(membershipType)!)
  const response = await fetch(`${BASE_URL}?${search.toString()}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch members: ${response.status}`)
  }
  return response.json() as Promise<AdminMemberListResponse>
}

/** The email is already on the list (409): `memberId` is the person who has it. */
export class DuplicateMemberError extends Error {
  memberId: number

  constructor(memberId: number) {
    super('Already on the list')
    this.name = 'DuplicateMemberError'
    this.memberId = memberId
  }
}

/** Add a person to the roster by hand (a volunteer, a helper): no membership is created. */
export async function addAdminMember(payload: { name: string; email?: string; phone?: string }): Promise<AdminMemberDetail> {
  const response = await fetch(BASE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(payload),
  })
  if (response.status === 409) {
    const body = (await response.json().catch(() => ({}))) as { member_id?: number }
    throw new DuplicateMemberError(body.member_id ?? 0)
  }
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<AdminMemberDetail>
}

export async function fetchAdminMember(id: number): Promise<AdminMemberDetail> {
  const response = await fetch(`${BASE_URL}/${id}`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch member: ${response.status}`)
  }
  return response.json() as Promise<AdminMemberDetail>
}

export interface DuplicateGroup {
  reason: 'email' | 'name_phone'
  members: AdminMemberSummary[]
}

export async function fetchDuplicateMembers(): Promise<{ groups: DuplicateGroup[] }> {
  const response = await fetch(`${BASE_URL}/duplicates`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch duplicates: ${response.status}`)
  }
  return response.json() as Promise<{ groups: DuplicateGroup[] }>
}

/** Folds `mergeId` into `keepId` (the record that survives). */
export async function mergeAdminMember(keepId: number, mergeId: number): Promise<AdminMemberDetail> {
  const response = await fetch(`${BASE_URL}/${keepId}/merge`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ merge_id: mergeId }),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    throw new Error(body.errors?.merge_id ?? `Merge failed: ${response.status}`)
  }
  return response.json() as Promise<AdminMemberDetail>
}

/** The members table as an .xlsx; takes the same filters as the list so the download matches what the page shows. */
/** Sends the welcome email to this member's address again; throws when it could not be sent. */
export async function resendMemberWelcomeEmail(memberId: number): Promise<{ sent_to: string }> {
  const response = await fetch(`${BASE_URL}/${memberId}/welcome-email`, { method: 'POST', headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<{ sent_to: string }>
}

export async function exportMembers(
  filter: { q?: string; status?: FilterValue; membershipType?: FilterValue } = {},
): Promise<Blob> {
  const search = new URLSearchParams()
  if (filter.q) search.set('q', filter.q)
  if (listParam(filter.status)) search.set('status', listParam(filter.status)!)
  if (listParam(filter.membershipType)) search.set('membership_type', listParam(filter.membershipType)!)
  const query = search.toString()
  const response = await fetch(`${BASE_URL}/export${query ? `?${query}` : ''}`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to export members: ${response.status}`)
  }
  return response.blob()
}

/** One person's personal data as a JSON file (access / portability request). */
export async function exportMemberPersonalData(id: number): Promise<Blob> {
  const response = await fetch(`${BASE_URL}/${id}/personal-data`, { headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to export personal data: ${response.status}`)
  }
  return response.blob()
}

export async function updateAdminMember(
  id: number,
  payload: AdminMemberProfilePayload,
): Promise<AdminMemberDetail> {
  const response = await fetch(`${BASE_URL}/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`Failed to update member: ${response.status}`)
  }
  return response.json() as Promise<AdminMemberDetail>
}

export async function createAdminFamilyMember(
  memberId: number,
  payload: FamilyMemberPayload,
): Promise<FamilyMember> {
  const response = await fetch(`${BASE_URL}/${memberId}/family`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<FamilyMember>
}

export async function updateAdminFamilyMember(
  memberId: number,
  familyMemberId: number,
  payload: FamilyMemberPayload,
): Promise<FamilyMember> {
  const response = await fetch(`${BASE_URL}/${memberId}/family/${familyMemberId}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<FamilyMember>
}

/** Record a person's request to be forgotten (sign-in stops now; anonymised after 30 days) or take it back. */
export async function setAdminMemberErase(id: number, action: 'erase-request' | 'erase-cancel'): Promise<AdminMemberDetail> {
  const response = await fetch(`${BASE_URL}/${id}/${action}`, { method: 'POST', headers: await authHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to update the erase request: ${response.status}`)
  }
  return response.json() as Promise<AdminMemberDetail>
}

export async function deleteAdminFamilyMember(memberId: number, familyMemberId: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/${memberId}/family/${familyMemberId}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to delete family member: ${response.status}`)
  }
}
