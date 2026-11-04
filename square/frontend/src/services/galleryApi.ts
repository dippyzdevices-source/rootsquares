import type { DescriptionStyle } from './settingsApi'
export interface MediaItem {
  id: number
  filename: string
  url: string
  thumbnail_url: string
  width: number
  height: number
  caption: string | null
}

import { optionalAuthHeaders } from './optionalAuthHeaders'

export interface AlbumSummary {
  description_style: DescriptionStyle | null
  id: number
  title: string
  description: string | null
  category: string | null
  year: number
  /** false only for an admin previewing an unpublished album. */
  published?: boolean
  cover_thumbnail_url: string | null
  cover_width: number | null
  cover_height: number | null
  photo_count: number
}

export interface AlbumListResponse {
  items: AlbumSummary[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface AlbumDetail {
  description_style: DescriptionStyle | null
  id: number
  title: string
  description: string | null
  event_id: number | null
  category: string | null
  published?: boolean
  media: MediaItem[]
}

export interface GalleryMediaItem extends MediaItem {
  album_id: number
  album_title: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export async function fetchAlbums(
  page = 1,
  perPage = 20,
  eventId?: number,
  category?: string,
): Promise<AlbumListResponse> {
  const search = new URLSearchParams({ page: String(page), per_page: String(perPage) })
  if (eventId) {
    search.set('event_id', String(eventId))
  }
  if (category) {
    search.set('category', category)
  }
  const response = await fetch(`${API_BASE_URL}/api/gallery/albums?${search.toString()}`, {
    headers: await optionalAuthHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch albums: ${response.status}`)
  }
  return response.json() as Promise<AlbumListResponse>
}

export interface ArchiveCoverageEra {
  era: string
  start_year: number
  end_year: number
  photo_count: number
  state: 'none' | 'very_few' | 'partial' | 'complete'
}

export async function fetchArchiveCoverage(): Promise<ArchiveCoverageEra[]> {
  const response = await fetch(`${API_BASE_URL}/api/gallery/coverage`)
  if (!response.ok) {
    throw new Error(`Failed to fetch archive coverage: ${response.status}`)
  }
  return ((await response.json()) as { items: ArchiveCoverageEra[] }).items
}

export async function fetchAlbum(id: number): Promise<AlbumDetail> {
  const response = await fetch(`${API_BASE_URL}/api/gallery/albums/${id}`, {
    headers: await optionalAuthHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch album: ${response.status}`)
  }
  return response.json() as Promise<AlbumDetail>
}

// A flat pool of individual photos across every published album (not one arbitrary "cover"
// per album) — used by the homepage hero carousel, see HomeView.vue.
export async function fetchGalleryMedia(limit = 40, random = false): Promise<GalleryMediaItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/gallery/media?limit=${limit}${random ? '&random=1' : ''}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch gallery media: ${response.status}`)
  }
  const data = (await response.json()) as { items: GalleryMediaItem[] }
  return data.items
}
