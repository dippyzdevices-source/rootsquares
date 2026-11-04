// Tests for formatEnum (4 cases), e.g. humanize; capitalizes the first letter of a plain lowercase value; replaces underscores and hyphens with spaces.
import { describe, it, expect } from 'vitest'
import { humanize } from '../formatEnum'

describe('humanize', () => {
  it('capitalizes the first letter of a plain lowercase value', () => {
    expect(humanize('cultural')).toBe('Cultural')
    expect(humanize('paid')).toBe('Paid')
  })

  it('replaces underscores and hyphens with spaces', () => {
    expect(humanize('event_ticket')).toBe('Event ticket')
    expect(humanize('already-used')).toBe('Already used')
  })

  it('handles an empty string without throwing', () => {
    expect(humanize('')).toBe('')
  })
})
