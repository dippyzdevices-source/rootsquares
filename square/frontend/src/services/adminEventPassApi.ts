// The Event pass of this square (rootsquares W11, ADR 044): the wrap-up page (summary and the export zip) and the message to every ticket buyer.
import { supabase } from './supabaseClient'

export interface EventPassSummary {
  phase: 'live' | 'archive' | ''
  live_until: string
  archive_until: string
  events: { id: number; title: string; slug: string }[]
  /** What the export zip holds, in words. */
  export: string[]
}

export interface BuyersCount {
  count: number
  max: number
}

export interface MessageBuyersPayload {
  event_id: number
  subject: string
  message: string
}

export interface MessageBuyersResult {
  sent: number
  failed: number
}

/** The server refused the message with a reason the person can read (no buyers, too many, e-mail not set up). */
export class MessageRefusedError extends Error {
  code: string

  constructor(message: string, code: string) {
    super(message)
    this.name = 'MessageRefusedError'
    this.code = code
  }
}

/** The message failed its checks: `errors` maps a field to its text. */
export class MessageInvalidError extends Error {
  errors: Record<string, string>

  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'MessageInvalidError'
    this.errors = errors
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchEventPass(): Promise<EventPassSummary> {
  const response = await fetch(`${API_BASE_URL}/api/admin/event-pass`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to fetch the Event pass: ${response.status}`)
  return response.json() as Promise<EventPassSummary>
}

/** The one zip with everything worth keeping (reports, lists, receipts). */
export async function downloadEventExport(): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/api/admin/event-pass/export`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to export: ${response.status}`)
  return response.blob()
}

export async function countBuyers(eventId: number): Promise<BuyersCount> {
  const response = await fetch(`${API_BASE_URL}/api/admin/tickets/buyers/count?event_id=${eventId}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to count the buyers: ${response.status}`)
  return response.json() as Promise<BuyersCount>
}

export async function messageBuyers(payload: MessageBuyersPayload): Promise<MessageBuyersResult> {
  const response = await fetch(`${API_BASE_URL}/api/admin/tickets/message-buyers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(payload),
  })
  if (response.ok) return response.json() as Promise<MessageBuyersResult>
  const body = (await response.json().catch(() => ({}))) as { error?: string; code?: string; errors?: Record<string, string> }
  if (response.status === 400 && body.errors) throw new MessageInvalidError(body.errors)
  throw new MessageRefusedError(body.error ?? `Request failed: ${response.status}`, body.code ?? '')
}
