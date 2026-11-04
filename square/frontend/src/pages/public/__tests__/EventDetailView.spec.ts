// Tests for EventDetailView (33 cases), e.g. EventDetailView; offers Donate and Become a sponsor only while the event accepts them; shows the event once loaded.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchEvent = vi.fn()
const mockFetchEventQr = vi.fn()
const mockFetchAlbums = vi.fn()
const mockFetchTicketTypes = vi.fn()
const mockFetchSupportOptions = vi.fn()

vi.mock('../../../services/eventSupportApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/eventSupportApi')>(
    '../../../services/eventSupportApi',
  )
  return { ...actual, fetchSupportOptions: (...args: unknown[]) => mockFetchSupportOptions(...args) }
})

vi.mock('../../../services/eventsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/eventsApi')>(
    '../../../services/eventsApi',
  )
  return { ...actual, fetchEvent: (...args: unknown[]) => mockFetchEvent(...args),
    fetchEventQr: (...args: unknown[]) => mockFetchEventQr(...args),
  }
})

vi.mock('../../../services/galleryApi', () => ({
  fetchAlbums: (...args: unknown[]) => mockFetchAlbums(...args),
}))

vi.mock('../../../services/ticketsApi', () => ({
  fetchTicketTypes: (...args: unknown[]) => mockFetchTicketTypes(...args),
}))

const mockDownloadEventIcs = vi.fn()
vi.mock('../../../utils/calendar', () => ({
  downloadEventIcs: (...args: unknown[]) => mockDownloadEventIcs(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { slug: 'durga-puja-2026' } }),
}))

import EventDetailView from '../EventDetailView.vue'
import { EventNotFoundError } from '../../../services/eventsApi'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

const baseEvent = {
  id: 1,
  title: 'Durga Puja 2026',
  slug: 'durga-puja-2026',
  short_description: null,
  event_type: 'festival',
  start_datetime: '2099-10-10T00:00:00Z',
  end_datetime: null,
  venue: null,
  banner_image: null,
  description: null,
  address: null,
  capacity: null,
  status: 'scheduled',
  sessions: [],
  published: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAlbums.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })
  mockFetchSupportOptions.mockResolvedValue({ open: false, donations_open: false, sponsorships_open: false, payment_methods: [] })
  mockFetchTicketTypes.mockResolvedValue({
    items: [
      {
        id: 1, name: 'Adult', description: null, price: 15000, capacity: null, remaining: null,
        sale_start: null, sale_end: null, members_only: false, status: 'on_sale',
      },
    ],
  })
})

describe('EventDetailView', () => {
  it('offers Donate and Become a sponsor only while the event accepts them', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    const closed = mount(EventDetailView, { global: { stubs } })
    await flushPromises()
    expect(closed.text()).not.toContain('Donate')
    expect(closed.text()).not.toContain('Become a sponsor')
    closed.unmount()

    mockFetchSupportOptions.mockResolvedValue({
      open: true, donations_open: true, sponsorships_open: true, payment_methods: ['vipps_qr'],
    })
    const open = mount(EventDetailView, { global: { stubs } })
    await flushPromises()
    expect(open.text()).toContain('Donate')
    expect(open.text()).toContain('Become a sponsor')
    expect(open.find('.event-head-donate').exists()).toBe(true)
    expect(open.find('.event-head-sponsor').text()).toContain('Become a sponsor')
    await open.find('.event-head-sponsor').trigger('click')
    await flushPromises()
    expect(new DOMWrapper(document.body).text()).toContain('Company or sponsor name')
    await open.find('.support-donate').trigger('click')
    await flushPromises()
    expect(new DOMWrapper(document.body).text()).toContain('Support Durga Puja 2026')
    open.unmount()
  })

  it('shows the event once loaded', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Durga Puja 2026')
  })

  it('shows a not-found state on a 404', async () => {
    mockFetchEvent.mockRejectedValue(new EventNotFoundError('durga-puja-2026'))

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Event not found')
  })

  it('does not show a Draft badge for a published event', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Draft')
  })

  it('shows a Draft badge when an admin is previewing an unpublished event', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, published: false })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Draft')
  })

  it('does not show slider controls with a single (or no) banner', async () => {
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      banners: [{ id: 1, image_url: 'https://x/one.jpg', sort_order: 0 }],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('button[aria-label="Next banner"]').exists()).toBe(false)
  })

  it('combines the legacy banner_image (shown first) with additional banners into one slider', async () => {
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      banner_image: 'https://x/main.jpg',
      banners: [{ id: 1, image_url: 'https://x/additional.jpg', sort_order: 0 }],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    const image = () => wrapper.find('.ds-banner-inner')
    expect(image().attributes('src')).toBe('https://x/main.jpg')
    expect(wrapper.find('button[aria-label="Next banner"]').exists()).toBe(true)

    await wrapper.find('button[aria-label="Next banner"]').trigger('click')
    expect(image().attributes('src')).toBe('https://x/additional.jpg')
  })

  it('cycles through multiple banners via next/previous controls', async () => {
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      banners: [
        { id: 1, image_url: 'https://x/one.jpg', sort_order: 0 },
        { id: 2, image_url: 'https://x/two.jpg', sort_order: 1 },
        { id: 3, image_url: 'https://x/three.jpg', sort_order: 2 },
      ],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    const image = () => wrapper.find('.ds-banner-inner')
    expect(image().attributes('src')).toBe('https://x/one.jpg')

    await wrapper.find('button[aria-label="Next banner"]').trigger('click')
    expect(image().attributes('src')).toBe('https://x/two.jpg')

    await wrapper.find('button[aria-label="Next banner"]').trigger('click')
    expect(image().attributes('src')).toBe('https://x/three.jpg')

    // Wraps back around to the first image.
    await wrapper.find('button[aria-label="Next banner"]').trigger('click')
    expect(image().attributes('src')).toBe('https://x/one.jpg')

    await wrapper.find('button[aria-label="Previous banner"]').trigger('click')
    expect(image().attributes('src')).toBe('https://x/three.jpg')
  })

  it('auto-advances the banner slider every 3s', async () => {
    vi.useFakeTimers()
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      banners: [
        { id: 1, image_url: 'https://x/one.jpg', sort_order: 0 },
        { id: 2, image_url: 'https://x/two.jpg', sort_order: 1 },
      ],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    const image = () => wrapper.find('.ds-banner-inner')
    expect(image().attributes('src')).toBe('https://x/one.jpg')

    await vi.advanceTimersByTimeAsync(3000)
    expect(image().attributes('src')).toBe('https://x/two.jpg')

    await vi.advanceTimersByTimeAsync(3000)
    expect(image().attributes('src')).toBe('https://x/one.jpg')

    wrapper.unmount()
    vi.useRealTimers()
  })

  it('pauses auto-advance while the pointer is hovering the banner, resuming on mouseleave', async () => {
    vi.useFakeTimers()
    // A real mouse-equipped device: (hover: hover) matches. Without this stub, jsdom has no
    // matchMedia at all (window.matchMedia is undefined), which the component now treats the
    // same as "no real hover" — see the touch-device test below, added for exactly that gap.
    vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
      matches: query === '(hover: hover)',
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })))
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      banners: [
        { id: 1, image_url: 'https://x/one.jpg', sort_order: 0 },
        { id: 2, image_url: 'https://x/two.jpg', sort_order: 1 },
      ],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    const image = () => wrapper.find('.ds-banner-inner')
    const banner = () => wrapper.find('.ds-banner')

    await banner().trigger('mouseenter')
    await vi.advanceTimersByTimeAsync(5000)
    expect(image().attributes('src')).toBe('https://x/one.jpg')

    await banner().trigger('mouseleave')
    await vi.advanceTimersByTimeAsync(3000)
    expect(image().attributes('src')).toBe('https://x/two.jpg')

    wrapper.unmount()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('does not pause auto-advance on a touch-only device (no real hover support), unlike a desktop mouse', async () => {
    // Mobile browsers fire a synthetic mouseenter on tap with no matching mouseleave ever
    // coming (there's no cursor to "leave") — without a (hover: hover) guard, the very first
    // tap on the banner (e.g. the swipe gesture itself) would permanently stop autoplay on
    // phones/tablets. Reported live: "3 sec scroll works on laptop but not on mobile devices."
    vi.useFakeTimers()
    vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
      matches: false, // (hover: hover) does not match a touch-only device
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })))
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      banners: [
        { id: 1, image_url: 'https://x/one.jpg', sort_order: 0 },
        { id: 2, image_url: 'https://x/two.jpg', sort_order: 1 },
      ],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    const image = () => wrapper.find('.ds-banner-inner')
    const banner = () => wrapper.find('.ds-banner')

    await banner().trigger('mouseenter') // the synthetic touch-tap mouseenter
    await vi.advanceTimersByTimeAsync(3000)
    expect(image().attributes('src')).toBe('https://x/two.jpg') // autoplay was NOT paused

    wrapper.unmount()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('pauses auto-advance while the lightbox is open', async () => {
    vi.useFakeTimers()
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      banners: [
        { id: 1, image_url: 'https://x/one.jpg', sort_order: 0 },
        { id: 2, image_url: 'https://x/two.jpg', sort_order: 1 },
      ],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('.ds-banner-frame').trigger('click')
    await flushPromises()

    const image = () => wrapper.find('.ds-banner-inner')
    await vi.advanceTimersByTimeAsync(5000)
    expect(image().attributes('src')).toBe('https://x/one.jpg')

    wrapper.unmount()
    vi.useRealTimers()
  })

  it('swipes to the next/previous banner on touch gestures, same as GalleryAlbumView', async () => {
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      banners: [
        { id: 1, image_url: 'https://x/one.jpg', sort_order: 0 },
        { id: 2, image_url: 'https://x/two.jpg', sort_order: 1 },
      ],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    const image = () => wrapper.find('.ds-banner-inner')
    const swipeSurface = () => wrapper.find('.ds-banner')
    expect(image().attributes('src')).toBe('https://x/one.jpg')

    await swipeSurface().trigger('touchstart', { touches: [{ clientX: 200 }] })
    await swipeSurface().trigger('touchend', { changedTouches: [{ clientX: 100 }] })
    expect(image().attributes('src')).toBe('https://x/two.jpg')

    await swipeSurface().trigger('touchstart', { touches: [{ clientX: 100 }] })
    await swipeSurface().trigger('touchend', { changedTouches: [{ clientX: 200 }] })
    expect(image().attributes('src')).toBe('https://x/one.jpg')
  })

  it('swipes to the next banner inside the lightbox modal too', async () => {
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      banners: [
        { id: 1, image_url: 'https://x/one.jpg', sort_order: 0 },
        { id: 2, image_url: 'https://x/two.jpg', sort_order: 1 },
      ],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('.ds-banner-frame').trigger('click')
    await flushPromises()

    // BaseModal renders via <Teleport to="body"> — query document.body directly, not
    // wrapper.find() (see CLAUDE.md's Teleport testing note).
    const body = new DOMWrapper(document.body)
    const modalImage = () => body.find('[role="dialog"] img')
    expect(modalImage().attributes('src')).toBe('https://x/one.jpg')

    await modalImage().trigger('touchstart', { touches: [{ clientX: 200 }] })
    await modalImage().trigger('touchend', { changedTouches: [{ clientX: 100 }] })
    expect(modalImage().attributes('src')).toBe('https://x/two.jpg')

    wrapper.unmount()
  })

  it('shows the same opaque prev/next buttons and dots inside the lightbox as the unzoomed banner, not a text counter', async () => {
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      banners: [
        { id: 1, image_url: 'https://x/one.jpg', sort_order: 0 },
        { id: 2, image_url: 'https://x/two.jpg', sort_order: 1 },
        { id: 3, image_url: 'https://x/three.jpg', sort_order: 2 },
      ],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('.ds-banner-frame').trigger('click')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    const dialog = () => body.find('[role="dialog"]')
    expect(dialog().text()).not.toMatch(/\d+\s*\/\s*\d+/)

    // .ds-icon-btn-scrim (not the plain transparent -onDark variant, which assumes a reliably
    // dark backdrop — untrue for a photo/matte in light theme) carries its own translucent
    // dark scrim so the controls stay legible regardless of theme or what's behind them,
    // while still reading as see-through rather than an opaque card.
    const nextButton = dialog().find('button[aria-label="Next banner"]')
    expect(nextButton.classes()).toContain('ds-icon-btn-scrim')
    expect(nextButton.classes()).not.toContain('ds-icon-btn-onDark')
    const prevButton = dialog().find('button[aria-label="Previous banner"]')
    expect(prevButton.classes()).toContain('ds-icon-btn-scrim')
    expect(prevButton.classes()).not.toContain('ds-icon-btn-onDark')
    expect(dialog().find('.ds-dot-bar').exists()).toBe(true)
    expect(dialog().findAll('.ds-testimonial-dot').length).toBe(3)

    const modalImage = () => body.find('[role="dialog"] img')
    expect(modalImage().attributes('src')).toBe('https://x/one.jpg')
    await nextButton.trigger('click')
    expect(modalImage().attributes('src')).toBe('https://x/two.jpg')

    await dialog().findAll('.ds-testimonial-dot')[2].trigger('click')
    expect(modalImage().attributes('src')).toBe('https://x/three.jpg')

    wrapper.unmount()
  })

  it('allows pinch-to-zoom in the lightbox instead of restricting touch to swipe-only', async () => {
    // touch-action: pan-y alone (no pinch-zoom) disables the browser's native pinch gesture —
    // reported live: "pinch to zoom does not work". pan-y is kept so the custom swipe gesture
    // still owns horizontal touch, but pinch-zoom must be included alongside it.
    mockFetchEvent.mockResolvedValue({ ...baseEvent, banner_image: 'https://x/main.jpg' })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()
    await wrapper.find('.ds-banner-frame').trigger('click')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    const scrollFrame = body.find('[role="dialog"] img').element.parentElement as HTMLElement
    expect(scrollFrame.style.touchAction).toContain('pinch-zoom')

    wrapper.unmount()
  })

  it('shrinks the lightbox modal to the photo itself via hug-content, not a fixed-width frame', async () => {
    // No letterboxing for a portrait photo comes from plain CSS shrink-to-fit on the modal
    // box itself (BaseModal's hug-content prop → .ds-modal-hug in design-system.css), not a
    // JS-computed pixel width — see that class's comment for why a prior JS-measurement
    // attempt here still left a wide fixed-size modal box around a narrow photo. This test
    // only verifies the prop is wired through; the actual shrink-to-fit behavior is native
    // browser layout, not something jsdom lays out, so it isn't asserted here.
    mockFetchEvent.mockResolvedValue({ ...baseEvent, banner_image: 'https://x/main.jpg' })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()
    await wrapper.find('.ds-banner-frame').trigger('click')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    expect(body.find('[role="dialog"]').classes()).toContain('ds-modal-hug')

    wrapper.unmount()
  })

  it('falls back to the legacy single banner_image when there are no banners', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, banner_image: 'https://x/legacy.jpg' })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.ds-banner-inner').attributes('src')).toBe('https://x/legacy.jpg')
  })

  it('groups schedule sessions under a day header', async () => {
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      sessions: [
        { id: 1, day_label: 'Friday', time: '18:00', title: 'Cultural Programme', description: null, sort_order: 0 },
        { id: 2, day_label: 'Friday', time: '20:00', title: 'Dinner', description: null, sort_order: 1 },
        { id: 3, day_label: 'Saturday', time: '10:00', title: 'Puja', description: null, sort_order: 2 },
      ],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    const headers = wrapper.findAll('h3').map((h) => h.text())
    expect(headers).toEqual(['Friday', 'Saturday'])
    expect(wrapper.text()).toContain('Cultural Programme')
    expect(wrapper.text()).toContain('Dinner')
    expect(wrapper.text()).toContain('Puja')
  })

  it('shows a schedule item description when set', async () => {
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      sessions: [
        { id: 1, day_label: 'Friday', time: '18:00', title: 'Cultural Programme', description: 'Traditional dance and music.', sort_order: 0 },
      ],
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Traditional dance and music.')
  })

  it('does not show a schedule section when there are no sessions', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Schedule')
  })

  it('downloads an .ics file when Add to calendar is clicked', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    const button = wrapper.find('button[title="Add to calendar"]')
    await button.trigger('click')

    expect(mockDownloadEventIcs).toHaveBeenCalledWith(
      expect.objectContaining({ id: baseEvent.id, title: baseEvent.title }),
    )
  })

  it('shows the Buy tickets link for a future event', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Buy tickets')
  })

  it('shows a Get directions link built from the venue and address', async () => {
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      venue: 'Oslo Concert Hall',
      address: 'Munkedamsveien 14, Oslo',
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    const link = wrapper.find('a[href*="google.com/maps"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe(
      'https://www.google.com/maps/dir/?api=1&destination=Oslo%20Concert%20Hall%2C%20Munkedamsveien%2014%2C%20Oslo',
    )
  })

  it('does not show a Get directions link when there is no venue or address', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('a[href*="google.com/maps"]').exists()).toBe(false)
  })

  it('hides the Buy tickets link when the event has no ticket types configured', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue({ items: [] })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(mockFetchTicketTypes).toHaveBeenCalledWith(baseEvent.id)
    expect(wrapper.text()).not.toContain('Buy tickets')
    expect(wrapper.text()).not.toContain('This event has already taken place.')
  })

  it('hides the Buy tickets link and shows a past-event message once the event has ended', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, start_datetime: '2020-01-01T00:00:00Z' })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Buy tickets')
    expect(wrapper.text()).toContain('This event has already taken place.')
  })

  it('fetches and shows albums tagged to this event', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchAlbums.mockResolvedValue({
      items: [{ id: 5, title: 'Durga Puja Photos', description: null, cover_thumbnail_url: null, photo_count: 3 }],
      page: 1,
      per_page: 20,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(mockFetchAlbums).toHaveBeenCalledWith(1, 20, baseEvent.id)
    expect(wrapper.text()).toContain('Durga Puja Photos')
  })

  it('does not show a Photos section when there are no tagged albums', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Photos')
  })

  it('uses end_datetime over start_datetime when both are present', async () => {
    mockFetchEvent.mockResolvedValue({
      ...baseEvent,
      start_datetime: '2020-01-01T00:00:00Z',
      end_datetime: '2099-01-01T00:00:00Z',
    })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Buy tickets')
  })

  it('shows Facebook/Instagram icons only when set, and Share opens a QR modal', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, facebook_url: 'https://facebook.com/events/1', instagram_url: null })
    mockFetchEventQr.mockResolvedValue({ url: 'https://x/events/durga-puja-2026', qr: 'data:image/png;base64,AAA' })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('a[href="https://facebook.com/events/1"]').exists()).toBe(true)
    expect(wrapper.find('a[aria-label="Instagram event page"]').exists()).toBe(false)

    await wrapper.find('button[aria-label="Share"]').trigger('click')
    await flushPromises()
    const body = new DOMWrapper(document.body)
    expect(body.find('img[alt="QR code for this event page"]').attributes('src')).toBe('data:image/png;base64,AAA')
    expect(body.text()).toContain('Copy link')
    wrapper.unmount()
  })

  it('keeps the event live but swaps Buy tickets for a closed note once the sales cut-off has passed', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, sales_closed: true, sales_close_at: '2026-10-09T18:00:00Z' })

    const wrapper = mount(EventDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain(baseEvent.title)
    expect(wrapper.text()).not.toContain('Buy tickets')
    expect(wrapper.text()).toContain('Ticket sales have closed.')
    expect(wrapper.text()).not.toContain('This event has already taken place.')
  })
})
