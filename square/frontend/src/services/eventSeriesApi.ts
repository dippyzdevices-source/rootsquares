// Recurring events and the calendar feed (wave 14 item 6, ADR 065).
import { supabase } from './supabaseClient'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/events`

export type SeriesFrequency = 'weekly' | 'monthly_weekday'

export interface SeriesRule {
  frequency: SeriesFrequency
  interval_weeks?: number
  /** 1 to 4 = the first to the fourth, 5 = the last (monthly_weekday only) */
  nth?: number
  until_date?: string | null
  max_count?: number | null
}

export interface SeriesOccurrence {
  id: number
  slug: string
  title: string
  start_datetime: string
  status: string
  published: boolean
  has_orders: boolean
}

export interface EventSeries {
  id: number
  frequency: SeriesFrequency
  interval_weeks: number
  nth: number | null
  until_date: string | null
  max_count: number | null
  ended: boolean
  label: string
  occurrences: SeriesOccurrence[]
}

export class SeriesValidationError extends Error {
  errors: Record<string, string>

  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'SeriesValidationError'
    this.errors = errors
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await supabase.auth.getSession()
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${data.session?.access_token ?? ''}`, 'Content-Type': 'application/json' },
  })
  const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string>; error?: string }
  if (response.status === 400 && body.errors) throw new SeriesValidationError(body.errors)
  if (!response.ok) throw new Error(body.error ?? `Request failed: ${response.status}`)
  return body as T
}

export const fetchEventSeries = (eventId: number) => call<{ series: EventSeries | null }>(`/${eventId}/series`)
export const repeatEvent = (eventId: number, rule: SeriesRule) => call<{ series: EventSeries; created: number }>(`/${eventId}/repeat`, { method: 'POST', body: JSON.stringify(rule) })
export const updateFollowingEvents = (eventId: number) => call<{ updated: number; skipped_with_orders: number }>(`/${eventId}/series/update-following`, { method: 'POST' })
export const endEventSeries = (eventId: number) => call<{ removed: number; cancelled: number }>(`/${eventId}/series/end`, { method: 'POST' })

/** The address of this site's calendar feed. The square is found from the host name, so it must be on the site's own host (a relative API base is made absolute). */
export function calendarFeedUrl(): string {
  const base = API_BASE_URL && /^https?:/.test(API_BASE_URL) ? API_BASE_URL : window.location.origin + (API_BASE_URL || '')
  return `${base.replace(/\/$/, '')}/api/events/calendar.ics`
}

/** The same address for a calendar app to subscribe to (webcal:// opens the calendar instead of downloading a file). */
export const calendarSubscribeUrl = () => calendarFeedUrl().replace(/^https?:/, 'webcal:')

/** One event as a calendar file. */
export function eventCalendarFileUrl(slug: string): string {
  return calendarFeedUrl().replace(/calendar\.ics$/, `${encodeURIComponent(slug)}/calendar.ics`)
}
