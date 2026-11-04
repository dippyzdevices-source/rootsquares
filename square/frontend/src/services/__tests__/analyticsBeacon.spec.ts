// The visit beacon of the public site (ADR 090, W23-R78): it sends nothing unless counting is on, never for an admin, a support session, the demo or a visitor who asked not to be
// tracked, and what it sends is only a path and a referrer. No cookie, no storage, no identifier.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { countedPath, resetBeacon, sendPageView, trackingRefused, type BeaconContext } from '../analyticsBeacon'

const on: BeaconContext = { enabled: true, isAdmin: false, inSupportSession: false, demo: false }

function fakeWindow(over: { dnt?: string; gpc?: boolean; referrer?: string } = {}) {
  const beacon = vi.fn().mockReturnValue(true)
  const win = {
    navigator: { doNotTrack: over.dnt ?? null, globalPrivacyControl: over.gpc, sendBeacon: beacon },
    document: { referrer: over.referrer ?? '' },
    location: { origin: 'https://club.example.org' },
    fetch: vi.fn(),
  } as unknown as Window
  return { win, beacon }
}
const sent = (beacon: ReturnType<typeof vi.fn>, n = 0) => beacon.mock.calls[n]![1] as Blob

beforeEach(() => resetBeacon())

describe('what is counted', () => {
  it('cuts query and fragment and leaves out the admin area, the API and sign-in pages', () => {
    expect(countedPath('/events/autumn?utm_source=mail#top')).toBe('/events/autumn')
    expect(countedPath('/')).toBe('/')
    for (const p of ['/admin', '/admin/events', '/api/x', '/login', '/register', '/support', '/auth/callback', '/Admin/News']) expect(countedPath(p)).toBeNull()
    expect(countedPath('/administration')).toBe('/administration') // only the real prefix, not a page that starts with the same letters
  })
})

describe('when nothing is sent', () => {
  it.each([
    ['counting is off', { ...on, enabled: false }],
    ['the visitor is a signed-in admin', { ...on, isAdmin: true }],
    ['it is a support session', { ...on, inSupportSession: true }],
    ['it is the demo', { ...on, demo: true }],
  ])('%s', (_name, ctx) => {
    const { win, beacon } = fakeWindow()
    expect(sendPageView('/events', '', ctx, win)).toBe(false)
    expect(beacon).not.toHaveBeenCalled()
  })

  it('the visitor asked not to be tracked (Do Not Track or Global Privacy Control)', () => {
    for (const over of [{ dnt: '1' }, { gpc: true }]) {
      const { win, beacon } = fakeWindow(over)
      expect(trackingRefused(win.navigator)).toBe(true)
      expect(sendPageView('/events', '', on, win)).toBe(false)
      expect(beacon).not.toHaveBeenCalled()
      resetBeacon()
    }
  })

  it('the page is not a public page, or it is the page that was just counted', () => {
    const { win, beacon } = fakeWindow()
    expect(sendPageView('/admin/news', '', on, win)).toBe(false)
    expect(sendPageView('/events', '', on, win)).toBe(true)
    expect(sendPageView('/events?page=2', '', on, win)).toBe(false) // the same page again (a query does not make a new page)
    expect(beacon).toHaveBeenCalledTimes(1)
  })
})

describe('what is sent', () => {
  it('only the path, and for the first page the referrer of the browser', async () => {
    const { win, beacon } = fakeWindow({ referrer: 'https://www.google.com/search?q=x' })
    expect(sendPageView('/events/autumn?id=7', '', on, win)).toBe(true)
    expect(JSON.parse(await sent(beacon).text())).toEqual({ path: '/events/autumn', referrer: 'https://www.google.com/search?q=x' })
  })

  it('a click inside the site sends the site itself as the referrer, so no new source is counted', async () => {
    const { win, beacon } = fakeWindow({ referrer: 'https://www.google.com/' })
    sendPageView('/', '', on, win)
    sendPageView('/events', '/', on, win)
    expect(JSON.parse(await sent(beacon, 1).text())).toEqual({ path: '/events', referrer: 'https://club.example.org/' })
  })

  it('is text/plain (no preflight), and never uses cookies or storage', () => {
    const { win, beacon } = fakeWindow()
    sendPageView('/', '', on, win)
    expect(sent(beacon).type).toBe('text/plain')
    expect(Object.keys(win)).not.toContain('localStorage')
    expect((win as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch).not.toHaveBeenCalled() // the beacon worked, so no second request
  })

  it('falls back to a keepalive request without credentials when the browser has no beacon, and never throws', () => {
    const { win } = fakeWindow()
    ;(win.navigator as unknown as { sendBeacon: unknown }).sendBeacon = undefined
    expect(sendPageView('/', '', on, win)).toBe(true)
    const init = (win.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0]![1] as RequestInit
    expect(init.keepalive).toBe(true)
    expect(init.credentials).toBe('omit')
    resetBeacon()
    ;(win as unknown as { fetch: unknown }).fetch = () => {
      throw new Error('offline')
    }
    expect(() => sendPageView('/events', '', on, win)).not.toThrow()
  })
})
