import { formatTicketDay } from './ticketDays'
import { isIsoDay } from './date'

export interface ScheduleDayGroup<T> {
  key: string
  label: string
  items: T[]
}

// Groups schedule items under their day, keeping the order the items arrive in (and the order the
// days first appear). A day stored as a date is shown like the ticket day headings ("Friday 16 Oct");
// a free-text day label is shown as typed.
export function groupSessionsByDay<T extends { day_label: string }>(items: T[]): ScheduleDayGroup<T>[] {
  const groups = new Map<string, ScheduleDayGroup<T>>()
  for (const item of items) {
    const key = item.day_label
    let group = groups.get(key)
    if (!group) {
      group = { key, label: isIsoDay(key) ? formatTicketDay(key) : key, items: [] }
      groups.set(key, group)
    }
    group.items.push(item)
  }
  return [...groups.values()]
}
