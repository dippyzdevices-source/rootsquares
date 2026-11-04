import { optionalAuthHeaders } from './optionalAuthHeaders'

export interface Sponsor {
  id: number
  name: string
  logo_url: string | null
  website_url: string | null
  /** false only for an admin previewing a hidden sponsor. */
  published?: boolean
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export async function fetchSponsors(): Promise<Sponsor[]> {
  const response = await fetch(`${API_BASE_URL}/api/sponsors`, { headers: await optionalAuthHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch sponsors: ${response.status}`)
  }
  return ((await response.json()) as { items: Sponsor[] }).items
}
