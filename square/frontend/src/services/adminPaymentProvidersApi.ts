import { supabase } from './supabaseClient'

const BASE_URL = `${import.meta.env.VITE_API_BASE_URL as string}/api/admin/payments/providers`

export interface ProviderStatus {
  provider: string
  connected: boolean
  mode?: 'test' | 'production'
  /** Non-secret facts only (the last characters of an id, the merchant number). */
  hint?: { client_id_last4?: string; msn?: string; key_last4?: string; restricted?: boolean }
  verified_at?: string | null
  webhook_registered?: boolean
}

export interface ProvidersView {
  /** Only the owner of the site may connect, replace or disconnect; any admin sees the status. */
  can_edit: boolean
  providers: { vipps: ProviderStatus; stripe: ProviderStatus }
}

export interface VippsKeys {
  client_id: string
  client_secret: string
  subscription_key: string
  msn: string
  mode: 'test' | 'production'
}

/** The server refused the keys: `errors` is per field, `_` is a message for the whole form. */
export class ProviderKeysError extends Error {
  errors: Record<string, string>
  constructor(errors: Record<string, string>) {
    super(errors._ ?? 'Could not save the keys')
    this.errors = errors
  }
}

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

async function read(response: Response): Promise<ProvidersView> {
  if (response.ok) return (await response.json()) as ProvidersView
  const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
  throw new ProviderKeysError(body.errors ?? { _: `Request failed: ${response.status}` })
}

export async function fetchProviders(): Promise<ProvidersView> {
  return read(await fetch(BASE_URL, { headers: await authHeaders() }))
}

/** Sends the keys once; the server tests them with Vipps and stores them encrypted. They are never sent back. */
export async function connectVipps(keys: VippsKeys): Promise<ProvidersView> {
  return read(await fetch(`${BASE_URL}/vipps`, { method: 'PUT', headers: await authHeaders(), body: JSON.stringify(keys) }))
}

export async function disconnectVipps(): Promise<ProvidersView> {
  return read(await fetch(`${BASE_URL}/vipps`, { method: 'DELETE', headers: await authHeaders() }))
}

/** Sends the Stripe key once; the server tests it with Stripe and stores it encrypted. It is never sent back. */
export interface StripeOptions {
  webhookSecret?: string
  /** Managed Payments (Stripe handles tax): needs a product tax code. */
  managedPayments?: boolean
  taxCode?: string
}

export async function connectStripe(secretKey: string, options: StripeOptions = {}): Promise<ProvidersView> {
  const webhookSecret = options.webhookSecret ?? ''
  const body: Record<string, string | boolean> = { secret_key: secretKey, managed_payments: !!options.managedPayments }
  if (options.managedPayments && options.taxCode?.trim()) body.tax_code = options.taxCode.trim()
  if (webhookSecret.trim()) body.webhook_secret = webhookSecret.trim()
  return read(await fetch(`${BASE_URL}/stripe`, { method: 'PUT', headers: await authHeaders(), body: JSON.stringify(body) }))
}

export async function disconnectStripe(): Promise<ProvidersView> {
  return read(await fetch(`${BASE_URL}/stripe`, { method: 'DELETE', headers: await authHeaders() }))
}
