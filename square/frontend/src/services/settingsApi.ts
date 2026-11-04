import type { HomeContent } from './siteContent'

export type DescriptionStyle = 'karla' | 'cormorant' | 'source'

export interface SiteSettings {
  contact_email: string
  contact_phone: string
  contact_address: string
  /** IANA time zone of the square, e.g. Europe/Oslo (W6-R54). */
  timezone?: string
  maintenance_mode: boolean
  /** Comma-separated event slugs, e.g. "mahalaya-2026,saraswati-2027". */
  maintenance_allowed_event_slugs: string
  /** Comma-separated page keys from a fixed set, e.g. "home,heritage" — see MAINTENANCE_PAGE_KEYS
   * in backend/app/settings/admin_routes.py and MAINTENANCE_PAGE_KEY_PATHS in router/index.ts. */
  maintenance_allowed_page_paths: string
  /** Comma-separated page keys switched OFF for everyone (admins included) while under construction. */
  maintenance_hidden_page_paths: string
  /** Public URL of the Heritage page hero photo; null until an admin uploads one. */
  heritage_image_url?: string | null
  /** Site-wide typeface for description text; applied as <html data-desc-style>. */
  description_style: DescriptionStyle
  /** The square's own legal texts (plain text); empty until it publishes them. */
  privacy_text?: string
  terms_text?: string
  /** The About (Heritage) page text; empty until the square writes it. */
  about_text?: string
  /** The square's own words for its home page, header and footer (W6-R64); keys as in HomeContent. */
  home_content?: Partial<HomeContent>
  /** Admin-only field (not in the public response): customers may use Vipps App payment. */
  vipps_app_public?: boolean
  vipps_qr_enabled?: boolean
  /** Public: the square's own Vipps number, only while Vipps QR is on and a number is set (null otherwise). Admin: the saved number. */
  vipps_number?: string | null
  /** Public: the picture of the square's Vipps QR code, only while Vipps QR is on (null otherwise). */
  vipps_qr_image_url?: string | null
  vipps_qr_available?: boolean
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
  /** Admin-only payment fees per method: convenience = charged to the customer, processing = taken by the provider. */
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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export async function fetchSettings(): Promise<SiteSettings> {
  const response = await fetch(`${API_BASE_URL}/api/settings`)
  if (!response.ok) {
    throw new Error(`Failed to fetch settings: ${response.status}`)
  }
  return response.json() as Promise<SiteSettings>
}
