// Tests for eventPhase (5 cases), e.g. eventPhase; is draft when unpublished, whatever the date; is live while a published event has not finished.
import { describe, it, expect } from 'vitest'
import { eventPhase } from '../eventPhase'

const NOW = new Date('2026-10-10T12:00:00')
const make = (published: boolean, start: string, end: string | null = null) => ({ published, start_datetime: start, end_datetime: end })

describe('eventPhase', () => {
  it('is draft when unpublished, whatever the date', () => {
    expect(eventPhase(make(false, '2026-12-01T10:00:00'), NOW)).toBe('draft')
    expect(eventPhase(make(false, '2025-01-01T10:00:00'), NOW)).toBe('draft')
  })

  it('is live while a published event has not finished', () => {
    expect(eventPhase(make(true, '2026-12-01T10:00:00'), NOW)).toBe('live')
    expect(eventPhase(make(true, '2026-10-09T10:00:00', '2026-10-11T18:00:00'), NOW)).toBe('live')
  })

  it('counts an event with no end time as live until the end of its start day', () => {
    expect(eventPhase(make(true, '2026-10-10T09:00:00'), NOW)).toBe('live')
    expect(eventPhase(make(true, '2026-10-09T09:00:00'), NOW)).toBe('expired')
  })

  it('is expired once a published event has ended', () => {
    expect(eventPhase(make(true, '2026-10-01T10:00:00', '2026-10-03T18:00:00'), NOW)).toBe('expired')
  })
})
