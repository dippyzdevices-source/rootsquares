// Tests for starterSuggestions (6 cases), e.g. starter suggestions (W14-R10); fits the kind of group and falls back to the cultural ones for a squar; reminds a religious community through its member list, since it sells.
import { describe, it, expect } from 'vitest'
import { suggestionsFor, availableReminderSuggestions, groupLabel } from '../starterSuggestions'

describe('starter suggestions (W14-R10)', () => {
  it('fits the kind of group and falls back to the cultural ones for a square made before starter sets', () => {
    expect(suggestionsFor('religious').donation_intro).toContain('gatherings')
    expect(suggestionsFor('cultural').donation_intro).toContain('traditions')
    expect(suggestionsFor('').donation_intro).toBe(suggestionsFor('cultural').donation_intro)
    expect(groupLabel('religious')).toBe('religious community')
    expect(groupLabel('')).toBe('')
  })

  it('reminds a religious community through its member list, since it sells no tickets to begin with', () => {
    expect(suggestionsFor('religious').reminders.map((r) => r.trigger)).toEqual(['event_before_members'])
    expect(suggestionsFor('cultural').reminders.map((r) => r.trigger)).toEqual(['event_before', 'membership_ending'])
  })

  it('fits bands and charities too', () => {
    expect(suggestionsFor('band').donation_intro).toContain('music')
    expect(suggestionsFor('charity').donation_intro).toContain('people who need us')
    expect(groupLabel('band')).toBe('band or artist')
    expect(groupLabel('charity')).toBe('charity or fundraiser')
    expect(suggestionsFor('band').reminders.map((r) => r.trigger)).toEqual(['event_before'])
  })

  it('every suggested reminder is a complete rule with the placeholders its trigger knows', () => {
    for (const group of ['cultural', 'religious', 'band', 'charity']) {
      for (const r of suggestionsFor(group).reminders) {
        expect(r.name && r.subject && r.body_html).toBeTruthy()
        expect(r.offset_days).toBeGreaterThanOrEqual(0)
        expect(r.send_hour).toBeGreaterThanOrEqual(0)
        expect(r.send_hour).toBeLessThanOrEqual(23)
      }
    }
  })

  it('offers only reminders whose modules are on (every module is on without a server answer)', () => {
    expect(availableReminderSuggestions('religious').length).toBe(1)
    expect(availableReminderSuggestions('cultural').length).toBe(2)
  })
})
