// Tests for HomeView (26 cases), e.g. HomeView — featured event section; shows the soonest upcoming event as the featured section, with a real; hides the featured section entirely when there are no upcoming events.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchEvents = vi.fn()
const mockFetchAlbums = vi.fn()
const mockFetchGalleryMedia = vi.fn()
const mockFetchNews = vi.fn()
const mockFetchTestimonials = vi.fn()

vi.mock('../../../services/eventsApi', () => ({
  fetchEvents: (...args: unknown[]) => mockFetchEvents(...args),
}))
vi.mock('../../../services/galleryApi', () => ({
  fetchAlbums: (...args: unknown[]) => mockFetchAlbums(...args),
  fetchGalleryMedia: (...args: unknown[]) => mockFetchGalleryMedia(...args),
}))
vi.mock('../../../services/newsApi', () => ({
  fetchNews: (...args: unknown[]) => mockFetchNews(...args),
}))
vi.mock('../../../services/testimonialsApi', () => ({
  fetchTestimonials: (...args: unknown[]) => mockFetchTestimonials(...args),
}))

const mockHomeContent = vi.fn()
vi.mock('../../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/siteContent')>()),
  loadHomeContent: () => mockHomeContent(),
}))

vi.mock('../../../services/sponsorsApi', () => ({ fetchSponsors: () => Promise.resolve([]) }))

import { fillHomeContent } from '../../../services/siteContent'
import HomeView from '../HomeView.vue'

// The square's own words for the testimonial and association band (W7-R7); a new square has none.
const BAND_WORDS = {
  testimonials_eyebrow: 'What our members say',
  testimonials_empty_text: "We're gathering stories from members — be one of the first to share yours.",
  testimonials_button: 'Share your story',
  association_eyebrow: 'The association',
  association_button: 'Read our story',
}

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
  mockHomeContent.mockResolvedValue(fillHomeContent(BAND_WORDS))
  mockFetchAlbums.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
  mockFetchGalleryMedia.mockResolvedValue([])
  mockFetchNews.mockResolvedValue({ items: [], page: 1, per_page: 2, total: 0, total_pages: 0 })
  mockFetchTestimonials.mockResolvedValue({ items: [] })
})

describe('HomeView — featured event section', () => {
  it('shows the soonest upcoming event as the featured section, with a real link', async () => {
    mockFetchEvents.mockResolvedValue({
      items: [
        {
          id: 1, title: 'Durga Puja 2026', slug: 'durga-puja-2026',
          short_description: 'Four days of celebration.', event_type: 'festival',
          start_datetime: '2026-10-10T00:00:00Z', end_datetime: null,
          venue: 'Furuset Forum', banner_image: null,
        },
      ],
      page: 1, per_page: 3, total: 1, total_pages: 1,
    })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Up next')
    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).toContain('Furuset Forum')
    expect(wrapper.find('a[href="/events/durga-puja-2026"]').exists()).toBe(true)
  })

  it('hides the featured section entirely when there are no upcoming events', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Up next')
  })
})

describe('HomeView — programme grid', () => {
  it("shows the event's banner image when it has one", async () => {
    mockFetchEvents.mockResolvedValue({
      items: [
        {
          id: 1, title: 'Durga Puja 2026', slug: 'durga-puja-2026',
          short_description: 'Four days of celebration.', event_type: 'festival',
          start_datetime: '2026-10-10T00:00:00Z', end_datetime: null,
          venue: 'Furuset Forum', banner_image: 'https://cdn.example.com/durga-puja.jpg',
        },
      ],
      page: 1, per_page: 3, total: 1, total_pages: 1,
    })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    const img = wrapper.find('.ds-event-media img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('https://cdn.example.com/durga-puja.jpg')
  })

  it('falls back to the placeholder when the event has no banner image', async () => {
    mockFetchEvents.mockResolvedValue({
      items: [
        {
          id: 1, title: 'Durga Puja 2026', slug: 'durga-puja-2026',
          short_description: 'Four days of celebration.', event_type: 'festival',
          start_datetime: '2026-10-10T00:00:00Z', end_datetime: null,
          venue: 'Furuset Forum', banner_image: null,
        },
      ],
      page: 1, per_page: 3, total: 1, total_pages: 1,
    })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.ds-event-media img').exists()).toBe(false)
    expect(wrapper.find('.ds-event-media.ds-placeholder').exists()).toBe(true)
  })
})

describe('HomeView — testimonials section', () => {
  it('shows testimonials when there are any', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchTestimonials.mockResolvedValue({
      items: [
        { id: 1, quote: 'BCA Oslo feels like family.', author_name: 'Priya Das', author_context: 'Member since 2020', photo_url: null },
      ],
    })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('What our members say')
    expect(wrapper.text()).toContain('BCA Oslo feels like family.')
    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('Member since 2020')
  })

  it('shows a "be the first to share" prompt instead of a quote when there are none yet', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('What our members say')
    expect(wrapper.text()).toContain('be one of the first to share yours')
  })

  it('shows no testimonial side, no buttons and no small lines until the square sets its words (W7-R7)', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockHomeContent.mockResolvedValue(fillHomeContent(undefined))

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('What our members say')
    expect(wrapper.text()).not.toContain('The association')
    expect(wrapper.find('a[href="/testimonials"]').exists()).toBe(false)
    expect(wrapper.find('a[href="/about"]').exists()).toBe(false)
  })

  it('always links to the public testimonial submission page', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('a[href="/testimonials"]').exists()).toBe(true)
  })

  it('renders "share your own story" as a real button, not a plain text link', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchTestimonials.mockResolvedValue({
      items: [
        { id: 1, quote: 'BCA Oslo feels like family.', author_name: 'Priya Das', author_context: null, photo_url: null },
      ],
    })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    const link = wrapper.find('a[href="/testimonials"]')
    expect(link.classes()).toContain('ds-btn')
  })

  it('does not show carousel navigation when there is only one testimonial', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchTestimonials.mockResolvedValue({
      items: [
        { id: 1, quote: 'BCA Oslo feels like family.', author_name: 'Priya Das', author_context: null, photo_url: null },
      ],
    })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.ds-testimonial-nav').exists()).toBe(false)
  })

  it('cycles through multiple testimonials via next/previous controls', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchTestimonials.mockResolvedValue({
      items: [
        { id: 1, quote: 'First quote.', author_name: 'Priya Das', author_context: null, photo_url: null },
        { id: 2, quote: 'Second quote.', author_name: 'Rahul Roy', author_context: null, photo_url: null },
      ],
    })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('First quote.')

    await wrapper.find('button[aria-label="Next testimonial"]').trigger('click')
    expect(wrapper.text()).toContain('Second quote.')

    await wrapper.find('button[aria-label="Previous testimonial"]').trigger('click')
    expect(wrapper.text()).toContain('First quote.')
  })

  it('auto-advances the testimonial carousel over time', async () => {
    vi.useFakeTimers()
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchTestimonials.mockResolvedValue({
      items: [
        { id: 1, quote: 'First quote.', author_name: 'Priya Das', author_context: null, photo_url: null },
        { id: 2, quote: 'Second quote.', author_name: 'Rahul Roy', author_context: null, photo_url: null },
      ],
    })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('First quote.')

    await vi.advanceTimersByTimeAsync(7000)
    expect(wrapper.text()).toContain('Second quote.')

    wrapper.unmount()
    vi.useRealTimers()
  })
})

function mediaItem(i: number) {
  return {
    id: i,
    filename: `photo${i}.jpg`,
    url: `https://example.com/${i}.jpg`,
    thumbnail_url: `https://example.com/${i}-thumb.jpg`,
    width: 800,
    height: 600,
    caption: null,
    album_id: i,
    album_title: `Album ${i}`,
  }
}

describe('HomeView — gallery preview', () => {
  it('shows the 3 most recent albums in the bottom "Moments" grid', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchAlbums.mockResolvedValue({
      items: Array.from({ length: 3 }, (_, i) => ({
        id: i + 1,
        title: `Album ${i + 1}`,
        cover_thumbnail_url: `https://example.com/${i + 1}.jpg`,
        photo_count: 5,
      })),
      page: 1, per_page: 3, total: 3, total_pages: 1,
    })

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.findAll('a.ds-gallery-item')).toHaveLength(3)
  })
})

describe('HomeView — hero gallery photos', () => {
  it('fetches from the flat gallery media pool, not per-album covers', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })

    mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(mockFetchGalleryMedia).toHaveBeenCalled()
    // The bottom "Moments" preview only ever needs its own 3 most recent albums directly.
    expect(mockFetchAlbums).toHaveBeenCalledWith(1, 3)
  })

  it('picks the hero photos from the whole media pool, spanning any number of albums', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchGalleryMedia.mockResolvedValue(Array.from({ length: 10 }, (_, i) => mediaItem(i + 1)))

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    // 1 large primary photo + a 3-up strip underneath.
    const heroImages = wrapper.findAll('.ds-hero-stage-shot img').filter((img) => (img.attributes('src') ?? '').includes('example.com'))
    expect(heroImages.length).toBe(4)
  })

  it('re-shuffles the hero photo set every 2s', async () => {
    vi.useFakeTimers()
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchGalleryMedia.mockResolvedValue(Array.from({ length: 10 }, (_, i) => mediaItem(i + 1)))

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    const primaryAlt = () => wrapper.find('.ds-hero-stage-shot img').attributes('alt')
    const seen = new Set([primaryAlt()])

    // With a pool of 10, seeing only 1 distinct primary photo across 20 reshuffles would be an
    // astronomically unlucky coincidence (~(1/10)^19) if reshuffling is actually happening —
    // this checks real behavior without assuming anything about Math.random/sort internals.
    for (let i = 0; i < 20; i++) {
      await vi.advanceTimersByTimeAsync(3000)
      await flushPromises()
      seen.add(primaryAlt())
    }
    expect(seen.size).toBeGreaterThan(1)

    wrapper.unmount()
    vi.useRealTimers()
  })

  it('pauses the hero photo carousel while a real mouse hovers it, resuming on mouseleave', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
      matches: query === '(hover: hover)',
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })))
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchGalleryMedia.mockResolvedValue(Array.from({ length: 10 }, (_, i) => mediaItem(i + 1)))

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    const primaryAlt = () => wrapper.find('.ds-hero-stage-shot img').attributes('alt')
    const heroWrap = wrapper.find('.ds-hero-stage-shot').element.parentElement!.parentElement!
    const firstAlt = primaryAlt()

    await heroWrap.dispatchEvent(new Event('mouseenter'))
    for (let i = 0; i < 10; i++) {
      await vi.advanceTimersByTimeAsync(3000)
      await flushPromises()
    }
    expect(primaryAlt()).toBe(firstAlt) // paused — no reshuffle at all while hovering

    await heroWrap.dispatchEvent(new Event('mouseleave'))
    const seenAfterResume = new Set([primaryAlt()])
    for (let i = 0; i < 20; i++) {
      await vi.advanceTimersByTimeAsync(3000)
      await flushPromises()
      seenAfterResume.add(primaryAlt())
    }
    expect(seenAfterResume.size).toBeGreaterThan(1) // resumed after mouseleave

    wrapper.unmount()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('shows a placeholder when the gallery has no photos yet', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchGalleryMedia.mockResolvedValue([])

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.ds-placeholder-glyph').exists()).toBe(true)
  })

  it('hides the 3-up thumbnail strip when fewer than 4 total photos exist, regardless of album count', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    // 2 photos from 2 different albums — total across the whole gallery is what matters, not
    // per-album covers.
    mockFetchGalleryMedia.mockResolvedValue([mediaItem(1), mediaItem(2)])

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    // Only the single primary photo — no strip, and no separate caption under it (HeroStage's
    // photo component uses the album title only as alt text, not a visible caption). Which of
    // the 2 photos lands as primary is randomized, so just assert it's one of the two.
    expect(wrapper.findAll('.ds-hero-stage-shot img')).toHaveLength(1)
    expect(['Album 1', 'Album 2']).toContain(wrapper.find('.ds-hero-stage-shot img').attributes('alt'))
    expect(wrapper.find('.ds-hero-stage-strip').exists()).toBe(false)
  })

  it('shows the 3-up thumbnail strip once there are 4+ photos, even from a single album', async () => {
    mockFetchEvents.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
    mockFetchGalleryMedia.mockResolvedValue([
      { ...mediaItem(1), album_id: 1, album_title: 'Durga Puja 2026' },
      { ...mediaItem(2), album_id: 1, album_title: 'Durga Puja 2026' },
      { ...mediaItem(3), album_id: 1, album_title: 'Durga Puja 2026' },
      { ...mediaItem(4), album_id: 1, album_title: 'Durga Puja 2026' },
    ])

    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.findAll('.ds-hero-stage-shot img')).toHaveLength(4)
    expect(wrapper.find('.ds-hero-stage-strip').exists()).toBe(true)
  })

  it('puts the DRAFT watermark class on a draft event card in the programme grid', async () => {
    const event = {
      id: 1, title: 'Durga Puja 2026', slug: 'durga-puja-2026', short_description: 'x', event_type: 'festival',
      start_datetime: '2026-10-10T00:00:00Z', end_datetime: null, venue: 'Furuset Forum', banner_image: null, published: true,
    }
    mockFetchEvents.mockResolvedValue({
      items: [event, { ...event, id: 2, title: 'Draft Puja', slug: 'draft-puja', published: false }],
      page: 1, per_page: 3, total: 2, total_pages: 1,
    })
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()

    const cards = wrapper.findAll('.ds-event-card')
    const draftCards = cards.filter((c) => c.classes().includes('ds-event-card-draft'))
    expect(draftCards.length).toBeGreaterThan(0)
    expect(draftCards.every((c) => c.text().includes('Draft Puja'))).toBe(true) // only the draft one
    expect(cards.some((c) => c.text().includes('Durga Puja 2026') && !c.classes().includes('ds-event-card-draft'))).toBe(true)
  })
})
