import { supabase } from './supabaseClient'
import { listParam, type FilterValue } from '../utils/filterParams'

export interface Subscriber {
  id: number
  email: string
  status: 'pending' | 'subscribed' | 'unsubscribed'
  consented_at: string | null
  unsubscribed_at: string | null
}

export interface SubscriberListResponse {
  items: Subscriber[]
  page: number
  per_page: number
  total: number
  total_pages: number
  subscribed_count: number
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/newsletter/subscribers`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchSubscribers(
  params: { q?: string; status?: FilterValue; page?: number; perPage?: number } = {},
): Promise<SubscriberListResponse> {
  const search = new URLSearchParams()
  if (params.q) search.set('q', params.q)
  if (listParam(params.status)) search.set('status', listParam(params.status)!)
  if (params.page) search.set('page', String(params.page))
  if (params.perPage) search.set('per_page', String(params.perPage))
  const response = await fetch(`${BASE_URL}?${search.toString()}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to fetch subscribers: ${response.status}`)
  return response.json() as Promise<SubscriberListResponse>
}

export async function exportSubscribers(status: FilterValue = '', q = ''): Promise<Blob> {
  const params = new URLSearchParams()
  if (listParam(status)) params.set('status', listParam(status)!)
  if (q) params.set('q', q)
  const search = params.toString() ? `?${params.toString()}` : ''
  const response = await fetch(`${BASE_URL}/export${search}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to export subscribers: ${response.status}`)
  return response.blob()
}

export async function deleteSubscriber(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/${id}`, { method: 'DELETE', headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to delete subscriber: ${response.status}`)
}

/** Uploads a picture for the newsletter body; resolves to its public URL. */
export async function uploadNewsletterImage(file: File): Promise<string> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${API_BASE_URL}/api/admin/newsletter/images`, {
    method: 'POST',
    headers: await authHeaders(),
    body: form,
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    throw new Error(body.errors?.file ?? 'Could not upload this picture.')
  }
  return ((await response.json()) as { url: string }).url
}
