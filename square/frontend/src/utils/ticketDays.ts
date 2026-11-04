export interface TicketDayGroup<T> {
  key: string
  // Empty when no ticket type has a date — the list is then shown flat, exactly as before.
  label: string
  items: T[]
}

// "Friday 23 Oct" for a "YYYY-MM-DD" date. Built from the parts so the time zone can't shift the day.
export function formatTicketDayShort(valueOn: string): string {
  const [y, m, d] = valueOn.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
}

export function formatTicketDay(valueOn: string): string {
  const [y, m, d] = valueOn.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' })
}

// Sections ticket types by the day they are for: dated days in order, then the undated ones
// ("All days"). If nothing is dated there is a single unlabelled group.
export function groupTicketsByDay<T extends { valid_on?: string | null }>(items: T[]): TicketDayGroup<T>[] {
  if (!items.some((item) => item.valid_on)) return [{ key: 'all', label: '', items }]
  const dated = new Map<string, T[]>()
  const undated: T[] = []
  for (const item of items) {
    if (item.valid_on) dated.set(item.valid_on, [...(dated.get(item.valid_on) ?? []), item])
    else undated.push(item)
  }
  const groups = [...dated.keys()].sort().map((day) => ({ key: day, label: formatTicketDay(day), items: dated.get(day)! }))
  if (undated.length) groups.push({ key: 'all', label: 'All days', items: undated })
  return groups
}
