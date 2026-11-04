export function formatEventDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

// Date + time together, e.g. "10 Oct 2026, 18:00" — for timestamps (like a check-in scan)
// where the time matters, not just the day.
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Converts a UTC ISO string to the "YYYY-MM-DDTHH:mm" format an
// <input type="datetime-local"> expects, in the browser's local time.
export function toDatetimeLocalValue(iso: string): string {
  const date = new Date(iso)
  const offsetMs = date.getTimezoneOffset() * 60 * 1000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

// Converts an <input type="datetime-local"> value (interpreted as the
// browser's local time) to a UTC ISO string for the API.
export function fromDatetimeLocalValue(value: string): string {
  return new Date(value).toISOString()
}

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/

// A schedule row's `day_label` is the ISO date picked in the admin calendar ("2026-10-09");
// older rows still hold free text ("Friday"). Dates show as "Friday, 9 Oct 2026", text as-is.
export function isIsoDay(value: string): boolean {
  return ISO_DAY.test(value)
}

export function formatScheduleDay(label: string): string {
  if (!isIsoDay(label)) return label
  return new Date(`${label}T12:00:00`).toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}
