// The Messages module (wave 14): messages to groups, reminder rules, the do-not-contact list, and the public unsubscribe call.
import { supabase } from './supabaseClient'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/messages`

export type MessageKind = 'update' | 'service'

export interface AudienceParam {
  name: string
  label: string
  type: 'event' | 'membership_type' | 'membership_status' | 'emails'
  required: boolean
}

export interface AudienceOption {
  key: string
  label: string
  description: string
  params: AudienceParam[]
}

export interface Trigger {
  key: string
  label: string
  placeholders: string[]
}

export interface MessageOptions {
  audiences: AudienceOption[]
  events: { id: number; title: string; start: string }[]
  membership_types: string[]
  membership_statuses: string[]
  triggers: Trigger[]
}

export interface AudienceChoice {
  type: string
  params: Record<string, string | number>
}

export interface AdminMessage {
  id: number
  kind: MessageKind
  channel: string
  subject: string
  body_html: string
  audience: AudienceChoice
  status: 'draft' | 'scheduled' | 'sending' | 'sent'
  source: string
  recipients_total: number
  sent_count: number
  failed_count: number
  skipped_count: number
  scheduled_for: string | null
  sent_at: string | null
  created_at: string
}

export interface MessagePayload {
  kind: MessageKind
  subject: string
  body_html: string
  audience: AudienceChoice
}

export interface AudiencePreview {
  total: number
  skipped: number
  will_receive: number
}

export interface MessageRecipientRow {
  id: number
  email: string
  name: string
  status: 'queued' | 'sending' | 'sent' | 'failed' | 'skipped'
}

export interface MessageRule {
  id: number
  name: string
  trigger: string
  offset_days: number
  send_hour: number
  enabled: boolean
  subject: string
  body_html: string
}

export type MessageRulePayload = Partial<Omit<MessageRule, 'id'>>

export interface Suppression {
  id: number
  email: string
  created_at: string
}

export class MessageValidationError extends Error {
  errors: Record<string, string>

  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'MessageValidationError'
    this.errors = errors
  }
}

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  return { Authorization: `Bearer ${data.session?.access_token ?? ''}`, 'Content-Type': 'application/json' }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers: { ...(await authHeaders()), ...(init.headers ?? {}) } })
  if (response.status === 204) return undefined as T
  const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string>; error?: string }
  if (response.status === 400 && body.errors) throw new MessageValidationError(body.errors)
  if (!response.ok) throw new Error(body.error ?? `Request failed: ${response.status}`)
  return body as T
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) })

export const fetchMessageOptions = () => call<MessageOptions>('/options')
export const previewAudience = (audience: AudienceChoice, kind: MessageKind) => call<AudiencePreview>('/preview', json('POST', { audience, kind }))
export const fetchMessages = (page = 1, audience = '') =>
  call<{ items: AdminMessage[]; total: number; page: number; per_page: number }>(`?page=${page}${audience ? `&audience=${encodeURIComponent(audience)}` : ''}`)
export const fetchMessage = (id: number) => call<AdminMessage>(`/${id}`)
export const createMessage = (payload: MessagePayload) => call<AdminMessage>('', json('POST', payload))
export const updateMessage = (id: number, payload: Partial<MessagePayload>) => call<AdminMessage>(`/${id}`, json('PATCH', payload))
export const deleteMessage = (id: number) => call<void>(`/${id}`, json('DELETE'))
export const sendTestMessage = (id: number, to?: string) => call<{ sent_to: string }>(`/${id}/send-test`, json('POST', to ? { to } : {}))
export const sendMessage = (id: number, scheduledFor?: string) => call<AdminMessage>(`/${id}/send`, json('POST', scheduledFor ? { scheduled_for: scheduledFor } : {}))
export const unscheduleMessage = (id: number) => call<AdminMessage>(`/${id}/unschedule`, json('POST'))
export const fetchMessageRecipients = (id: number, status = '', page = 1) =>
  call<{ items: MessageRecipientRow[]; total: number; page: number; per_page: number }>(`/${id}/recipients?page=${page}${status ? `&status=${status}` : ''}`)

export const fetchRules = () => call<{ items: MessageRule[] }>('/rules')
export const createRule = (payload: MessageRulePayload) => call<MessageRule>('/rules', json('POST', payload))
export const updateRule = (id: number, payload: MessageRulePayload) => call<MessageRule>(`/rules/${id}`, json('PATCH', payload))
export const deleteRule = (id: number) => call<void>(`/rules/${id}`, json('DELETE'))

export const fetchSuppressions = () => call<{ items: Suppression[] }>('/suppressions')
export const addSuppressions = (emails: string) => call<{ added: number }>('/suppressions', json('POST', { emails }))
export const removeSuppression = (id: number) => call<void>(`/suppressions/${id}`, json('DELETE'))

/** The unsubscribe link in an e-mail: true = the address is now on the do-not-contact list, false = the link is not valid. */
export async function unsubscribeFromMessages(email: string, token: string): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/api/messages/unsubscribe?e=${encodeURIComponent(email)}&t=${encodeURIComponent(token)}`, { method: 'POST' })
  if (response.status === 400) return false
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return true
}
