import { optionalAuthHeaders } from './optionalAuthHeaders'

export interface CommitteeMember {
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
  /** false only for an admin previewing a hidden member. */
  published?: boolean
}

export interface CommitteeListResponse {
  items: CommitteeMember[]
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export async function fetchCommittee(): Promise<CommitteeListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/committee`, { headers: await optionalAuthHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch committee: ${response.status}`)
  }
  return response.json() as Promise<CommitteeListResponse>
}
