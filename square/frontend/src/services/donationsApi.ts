// The Donations module (wave 14): the public page's calls and the admin's.
import { supabase } from './supabaseClient'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export type DonationMethod = 'app' | 'card' | 'qr' | 'bank' | 'cash'

export interface BankDetails {
  holder: string
  bank_name: string
  account_number: string
  iban: string
  bic: string
  note: string
}

export interface DonationConfig {
  open: boolean
  methods: DonationMethod[]
  amounts: number[]
  min_amount: number
  currency: string
  intro: string
  thanks: string
  vipps_number: string
  vipps_qr_image_url?: string | null
  bank: BankDetails | null
  cash_note: string
  surcharge_percent: number
  /** The fee on a card gift, in percent (0 when card is not offered). */
  card_surcharge_percent?: number
}

export interface DonationPayload {
  donor_name: string
  donor_email: string
  amount: number
  payment_method: DonationMethod
  anonymous: boolean
  message?: string
}

export interface DonationResult {
  reference: string
  amount: number
  currency: string
  status: string
  donor_name: string
  redirect_url?: string
  surcharge_amount?: number
}

export class DonationValidationError extends Error {
  errors: Record<string, string>

  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'DonationValidationError'
    this.errors = errors
  }
}

export async function fetchDonationConfig(): Promise<DonationConfig> {
  const response = await fetch(`${API_BASE_URL}/api/donations/config`)
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<DonationConfig>
}

export async function giveDonation(payload: DonationPayload): Promise<DonationResult> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const { data } = await supabase.auth.getSession()
  if (data.session?.access_token) headers.Authorization = `Bearer ${data.session.access_token}`
  const response = await fetch(`${API_BASE_URL}/api/donations`, { method: 'POST', headers, body: JSON.stringify(payload) })
  const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string>; error?: string }
  if (response.status === 400 && body.errors) throw new DonationValidationError(body.errors)
  if (!response.ok) throw new Error(body.error ?? `Request failed: ${response.status}`)
  return body as unknown as DonationResult
}

export async function confirmDonationPayment(reference: string, email: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/donations/${encodeURIComponent(reference)}/confirm-payment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
}

// ---- admin ----

export interface AdminDonation {
  id: number
  reference: string
  donor_name: string
  donor_email: string
  anonymous: boolean
  message: string | null
  amount: number
  currency: string
  status: string
  payment_method: string | null
  created_at: string
  paid_at: string | null
}

export interface AdminDonationList {
  items: AdminDonation[]
  total: number
  page: number
  per_page: number
  paid_total: number
}

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  return { Authorization: `Bearer ${data.session?.access_token ?? ''}` }
}

export async function fetchAdminDonations(filter: { q?: string; status?: string; page?: number } = {}): Promise<AdminDonationList> {
  const search = new URLSearchParams()
  if (filter.q) search.set('q', filter.q)
  if (filter.status) search.set('status', filter.status)
  if (filter.page) search.set('page', String(filter.page))
  const query = search.toString()
  const response = await fetch(`${API_BASE_URL}/api/admin/donations${query ? `?${query}` : ''}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to load donations: ${response.status}`)
  return response.json() as Promise<AdminDonationList>
}

export async function exportDonations(filter: { q?: string; status?: string } = {}): Promise<Blob> {
  const search = new URLSearchParams()
  if (filter.q) search.set('q', filter.q)
  if (filter.status) search.set('status', filter.status)
  const query = search.toString()
  const response = await fetch(`${API_BASE_URL}/api/admin/donations/export${query ? `?${query}` : ''}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to export donations: ${response.status}`)
  return response.blob()
}

export async function adminDonationAction(id: number, action: 'mark-paid' | 'reject', method?: 'cash' | 'vipps_qr' | 'bank_transfer'): Promise<AdminDonation> {
  const response = await fetch(`${API_BASE_URL}/api/admin/donations/${id}/${action}`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(method ? { payment_method: method } : {}),
  })
  if (!response.ok) throw new Error(`Failed to update the donation: ${response.status}`)
  return response.json() as Promise<AdminDonation>
}
