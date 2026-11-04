import { squareProfile } from '../services/squareConfig'

export interface IcsEventInput {
  id: number
  title: string
  description?: string | null
  startDatetime: string
  endDatetime?: string | null
  venue?: string | null
  address?: string | null
}

function toIcsDateTime(iso: string): string {
  return new Date(iso).toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z'
}

// RFC 5545 TEXT escaping — backslash first, so it doesn't double-escape the others.
function escapeIcsText(text: string): string {
  return text
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n')
}

export function buildEventIcs(event: IcsEventInput): string {
  const location = [event.venue, event.address].filter(Boolean).join(', ')
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    `PRODID:-//${squareProfile.name}//Events//EN`,
    'BEGIN:VEVENT',
    `UID:event-${event.id}@${window.location.hostname}`, // unique per site: the square's own host name (bca-oslo wrote @bcaoslo.no)
    `DTSTAMP:${toIcsDateTime(new Date().toISOString())}`,
    `DTSTART:${toIcsDateTime(event.startDatetime)}`,
    `DTEND:${toIcsDateTime(event.endDatetime ?? event.startDatetime)}`,
    `SUMMARY:${escapeIcsText(event.title)}`,
  ]
  if (event.description) lines.push(`DESCRIPTION:${escapeIcsText(event.description)}`)
  if (location) lines.push(`LOCATION:${escapeIcsText(location)}`)
  lines.push('END:VEVENT', 'END:VCALENDAR')
  // RFC 5545 requires CRLF line endings.
  return lines.join('\r\n')
}

export function downloadEventIcs(event: IcsEventInput): void {
  const blob = new Blob([buildEventIcs(event)], { type: 'text/calendar;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${event.title.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.ics`
  link.click()
  URL.revokeObjectURL(url)
}
