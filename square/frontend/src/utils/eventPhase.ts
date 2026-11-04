// Where an event is in its life, for the admin pills and filters:
//   draft   — not published yet (whatever its date)
//   live    — published and not over yet (an event with no end time counts until the end of its start day)
//   expired — published and over
export type EventPhase = 'draft' | 'live' | 'expired'

export const EVENT_PHASE_LABEL: Record<EventPhase, string> = { draft: 'Draft', live: 'Live', expired: 'Expired' }
export const EVENT_PHASE_BADGE: Record<EventPhase, string> = {
  draft: 'ds-badge-accent',
  live: 'ds-badge-success',
  expired: 'ds-badge-neutral',
}

export function eventPhase(event: { published: boolean; start_datetime: string; end_datetime: string | null }, now = new Date()): EventPhase {
  if (!event.published) return 'draft'
  let over: Date
  if (event.end_datetime) {
    over = new Date(event.end_datetime)
  } else {
    over = new Date(event.start_datetime)
    over.setHours(23, 59, 59, 999)
  }
  return over.getTime() < now.getTime() ? 'expired' : 'live'
}
