import { supabase } from './supabaseClient'

interface FollowUpPerson {
  membership_id: number
  member_id: number
  name: string
  email: string | null
  phone: string | null
  membership_type: string
  /** When the last reminder email went out (ISO), or null if none yet. */
  last_reminded_at: string | null
  /** False for 3 days after a reminder, so nobody is mailed twice by accident. */
  can_remind: boolean
}

/** Asked for a membership, hasn't paid the first period yet. */
export interface FollowUpRequest extends FollowUpPerson {
  period_label: string | null
  /** Øre. */
  amount: number
  requested_at: string
  days_waiting: number
}

/** Active member with unpaid periods that have started. */
export interface FollowUpDue extends FollowUpPerson {
  due_count: number
  /** Øre. */
  due_total: number
  due_labels: string[]
  days_overdue: number
}

export interface FollowUpResponse {
  requests: FollowUpRequest[]
  dues: FollowUpDue[]
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/membership-follow-up`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function failure(response: Response, fallback: string): Promise<Error> {
  const body = (await response.json().catch(() => ({}))) as { error?: string }
  return new Error(body.error ?? fallback)
}

export async function fetchFollowUp(): Promise<FollowUpResponse> {
  const response = await fetch(BASE_URL, { headers: await authHeaders() })
  if (!response.ok) throw await failure(response, `Failed to load follow-up list: ${response.status}`)
  return response.json() as Promise<FollowUpResponse>
}

export async function sendFollowUpReminder(membershipId: number): Promise<{ last_reminded_at: string }> {
  const response = await fetch(`${BASE_URL}/${membershipId}/reminder`, {
    method: 'POST',
    headers: await authHeaders(),
  })
  if (!response.ok) throw await failure(response, 'Could not send the reminder')
  return response.json() as Promise<{ last_reminded_at: string }>
}

export async function removeFollowUpRequest(membershipId: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/${membershipId}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) throw await failure(response, 'Could not remove the request')
}
