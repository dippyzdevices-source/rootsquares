// Tests for eventSeriesApi (2 cases), e.g. calendar addresses; are on the site\.
import { describe, it, expect } from 'vitest'
import { calendarFeedUrl, calendarSubscribeUrl, eventCalendarFileUrl } from '../eventSeriesApi'

describe('calendar addresses', () => {
  it('are on the site\'s own host (the square is found from the host name), and webcal:// for subscribing', () => {
    const feed = calendarFeedUrl()
    expect(feed).toMatch(/^https?:\/\/.+\/api\/events\/calendar\.ics$/)
    expect(calendarSubscribeUrl()).toBe(feed.replace(/^https?:/, 'webcal:'))
    expect(eventCalendarFileUrl('sunday service')).toMatch(/\/api\/events\/sunday%20service\/calendar\.ics$/)
  })
})
