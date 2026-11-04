import { supabase } from './supabaseClient'
import type { DescriptionStyle, SiteSettings } from './settingsApi'
import type { HomeContent } from './siteContent'

export interface SiteSettingsPayload {
  contact_email?: string
  contact_phone?: string
  contact_address?: string
  timezone?: string
  maintenance_mode?: boolean
  maintenance_allowed_event_slugs?: string
  maintenance_allowed_page_paths?: string
  maintenance_hidden_page_paths?: string
  description_style?: DescriptionStyle
  vipps_app_public?: boolean
  vipps_qr_enabled?: boolean
  /** The square's own Vipps number (digits); an empty string clears it. */
  vipps_number?: string | null
  privacy_text?: string
  terms_text?: string
  about_text?: string
  home_content?: Partial<HomeContent>
  cash_enabled?: boolean
  cash_ticket_note?: string
  cash_membership_note?: string
  bank_transfer_enabled?: boolean
  bank_account_holder?: string
  bank_name?: string
  bank_account_number?: string
  bank_iban?: string
  bank_bic?: string
  bank_transfer_note?: string
  bank_transfer_available?: boolean
  donation_amounts?: string
  donation_intro?: string
  donation_thanks?: string
  message_footer_update?: string
  message_footer_service?: string
  vipps_qr_convenience_percent?: number
  vipps_qr_processing_percent?: number
  vipps_qr_processing_fixed_ore?: number
  vipps_app_convenience_percent?: number
  vipps_app_processing_percent?: number
  vipps_app_processing_fixed_ore?: number
  cash_convenience_percent?: number
  cash_processing_percent?: number
  cash_processing_fixed_ore?: number
}

export class ValidationError extends Error {
  errors: Record<string, string>

  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'ValidationError'
    this.errors = errors
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/settings`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
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

export async function fetchAdminSettings(): Promise<SiteSettings> {
  const response = await fetch(BASE_URL, { headers: await authHeaders() })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<SiteSettings>
}

export async function updateAdminSettings(payload: SiteSettingsPayload): Promise<SiteSettings> {
  const response = await fetch(BASE_URL, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<SiteSettings>
}

/** The picture of the square's own Vipps QR code. */
export async function uploadVippsQrImage(file: File): Promise<SiteSettings> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${BASE_URL}/vipps-qr-image`, { method: 'POST', headers: await authHeaders(), body: formData })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<SiteSettings>
}

export async function deleteVippsQrImage(): Promise<SiteSettings> {
  const response = await fetch(`${BASE_URL}/vipps-qr-image`, { method: 'DELETE', headers: await authHeaders() })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<SiteSettings>
}

export async function uploadHeritageImage(file: File): Promise<SiteSettings> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${BASE_URL}/heritage-image`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<SiteSettings>
}
