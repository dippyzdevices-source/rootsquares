import { ValidationError } from './membershipDriveApi'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export type DonationMethod = 'vipps_app' | 'stripe' | 'vipps_qr'

export interface SupportOptions {
  /** The event is published and not over yet. */
  open: boolean
  donations_open: boolean
  sponsorships_open: boolean
  payment_methods: DonationMethod[]
}

export interface DonationPayload {
  name?: string
  email?: string
  /** Øre. */
  amount: number
  payment_method: DonationMethod
}

export interface SponsorshipPayload {
  name: string
  contact_name: string
  email: string
  phone?: string
  website?: string
  /** Øre; optional. */
  amount?: number
  requirements?: string
}

const CLOSED: SupportOptions = { open: false, donations_open: false, sponsorships_open: false, payment_methods: [] }

export async function fetchSupportOptions(slug: string): Promise<SupportOptions> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/events/${slug}/support/options`)
    if (!response.ok) return CLOSED
    return (await response.json()) as SupportOptions
  } catch {
    return CLOSED
  }
}

async function post<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (response.status === 400) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    if (body.errors) throw new ValidationError(body.errors)
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string }
    throw new Error(body.error ?? 'Something went wrong. Please try again.')
  }
  return response.json() as Promise<T>
}

export function donate(slug: string, payload: DonationPayload) {
  return post<{ payment_method: DonationMethod; redirect_url: string | null }>(
    `/api/events/${slug}/support/donations`,
    payload,
  )
}

export function enquireSponsorship(slug: string, payload: SponsorshipPayload) {
  return post<{ ok: boolean }>(`/api/events/${slug}/support/sponsorships`, payload)
}
