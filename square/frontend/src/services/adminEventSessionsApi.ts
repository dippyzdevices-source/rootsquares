import { supabase } from './supabaseClient'
import type { EventSessionRecord } from './eventsApi'

export interface EventSessionPayload {
  day_label?: string
  time?: string
  title?: string
  description?: string | null
  sort_order?: number
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

export async function createEventSession(
  eventId: number,
  payload: EventSessionPayload,
): Promise<EventSessionRecord> {
  const response = await fetch(`${API_BASE_URL}/api/admin/events/${eventId}/sessions`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<EventSessionRecord>
}

export async function updateEventSession(
  eventId: number,
  sessionId: number,
  payload: EventSessionPayload,
): Promise<EventSessionRecord> {
  const response = await fetch(
    `${API_BASE_URL}/api/admin/events/${eventId}/sessions/${sessionId}`,
    {
      method: 'PATCH',
      headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<EventSessionRecord>
}

export async function deleteEventSession(eventId: number, sessionId: number): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/admin/events/${eventId}/sessions/${sessionId}`,
    { method: 'DELETE', headers: await authHeaders() },
  )
  if (!response.ok) {
    throw new Error(`Failed to delete session: ${response.status}`)
  }
}
