import type { DescriptionStyle } from './settingsApi'
import { optionalAuthHeaders } from './optionalAuthHeaders'

export interface Magazine {
  id: number
  title: string
  slug: string
  issue_label: string | null
  issue_date: string | null
  description: string | null
  description_style: DescriptionStyle | null
  pdf_url: string | null
  cover_url: string | null
  /** false only for an admin previewing an unpublished magazine. */
  published?: boolean
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export async function fetchMagazines(): Promise<Magazine[]> {
  const response = await fetch(`${API_BASE_URL}/api/magazines`, { headers: await optionalAuthHeaders() })
  if (!response.ok) {
    throw new Error(`Failed to fetch magazines: ${response.status}`)
  }
  return ((await response.json()) as { items: Magazine[] }).items
}

export async function fetchMagazine(slug: string): Promise<Magazine> {
  const response = await fetch(`${API_BASE_URL}/api/magazines/${encodeURIComponent(slug)}`, {
    headers: await optionalAuthHeaders(),
  })
  if (response.status === 404) {
    throw new Error('not_found')
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch magazine: ${response.status}`)
  }
  return (await response.json()) as Magazine
}
