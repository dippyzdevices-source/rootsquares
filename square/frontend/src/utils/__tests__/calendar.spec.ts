// Tests for calendar (6 cases), e.g. buildEventIcs; builds a valid VCALENDAR block with the event details; falls back to the start time for DTEND when there is no end_datetime.
import { describe, it, expect } from 'vitest'
import { buildEventIcs } from '../calendar'

describe('buildEventIcs', () => {
  it('builds a valid VCALENDAR block with the event details', () => {
    const ics = buildEventIcs({
      id: 1,
      title: 'Durga Puja 2026',
      description: 'Four days of celebration.',
      startDatetime: '2026-10-10T10:00:00Z',
      endDatetime: '2026-10-10T18:00:00Z',
      venue: 'Oslo Concert Hall',
      address: 'Munkedamsveien 14, Oslo',
    })

    expect(ics).toContain('BEGIN:VCALENDAR')
    expect(ics).toContain('END:VCALENDAR')
    expect(ics).toContain(`UID:event-1@${window.location.hostname}`)
    expect(ics).toContain('DTSTART:20261010T100000Z')
    expect(ics).toContain('DTEND:20261010T180000Z')
    expect(ics).toContain('SUMMARY:Durga Puja 2026')
    expect(ics).toContain('DESCRIPTION:Four days of celebration.')
    expect(ics).toContain('LOCATION:Oslo Concert Hall\\, Munkedamsveien 14\\, Oslo')
  })

  it('falls back to the start time for DTEND when there is no end_datetime', () => {
    const ics = buildEventIcs({
      id: 2,
      title: 'Saraswati Puja',
      startDatetime: '2026-02-01T09:00:00Z',
      endDatetime: null,
    })

    expect(ics).toContain('DTSTART:20260201T090000Z')
    expect(ics).toContain('DTEND:20260201T090000Z')
  })

  it('escapes commas and semicolons in text fields', () => {
    const ics = buildEventIcs({
      id: 3,
      title: 'Event; Special, Edition',
      startDatetime: '2026-01-01T00:00:00Z',
    })

    expect(ics).toContain('SUMMARY:Event\\; Special\\, Edition')
  })

  it('omits DESCRIPTION and LOCATION when not provided', () => {
    const ics = buildEventIcs({
      id: 4,
      title: 'No Venue Event',
      startDatetime: '2026-01-01T00:00:00Z',
    })

    expect(ics).not.toContain('DESCRIPTION:')
    expect(ics).not.toContain('LOCATION:')
  })
  it('makes the event UID from the site host name, not a fixed domain (W6-R54)', () => {
    const ics = buildEventIcs({ id: 7, title: 'T', startDatetime: '2026-10-10T10:00:00Z' })
    expect(ics).toContain(`UID:event-7@${window.location.hostname}`)
    expect(ics).not.toContain('bcaoslo')
  })
})
