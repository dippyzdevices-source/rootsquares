import { optionalAuthHeaders } from './optionalAuthHeaders'

export interface Founder {
  id: number
  name: string
  sub_name: string | null
  role: string
  quote: string
  portrait_url: string | null
  /** false only for an admin previewing a hidden founder. */
  published?: boolean
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export async function fetchFounders(): Promise<Founder[]> {
  const response = await fetch(`${API_BASE_URL}/api/founders`, { headers: await optionalAuthHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch founders: ${response.status}`)
  }
  return ((await response.json()) as { items: Founder[] }).items
}
