// Generic fallback for displaying a raw backend enum/status string (e.g. "event_ticket",
// "cultural") as sentence-case text instead of the raw lowercase value. Domain-specific labels
// that need a real semantic relabel (not just casing) — like ticketStatus.ts turning "used"
// into "Checked in" — should keep their own dedicated helper instead of this one.
export function humanize(value: string): string {
  const spaced = value.replace(/[_-]+/g, ' ').trim()
  if (!spaced) return spaced
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}
