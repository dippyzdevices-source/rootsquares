// Tests for EventsOff (3 cases), e.g. Home page and the Events module; on: programme, Up next card and the programme button are there; off: none of it, no request, no link to /events.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Events module (W8-R28): no programme, no Up next card, no button to the programme, and events are not asked for.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/modules')>()),
  moduleEnabled: (key?: string) => !off.keys.includes(key ?? ''),
  offeredPhrase: () => '',
}))
const mockEvents = vi.fn()
vi.mock('../../../services/eventsApi', () => ({ fetchEvents: (...a: unknown[]) => mockEvents(...a) }))
vi.mock('../../../services/galleryApi', () => ({ fetchAlbums: () => Promise.resolve({ items: [] }), fetchGalleryMedia: () => Promise.resolve([]) }))
vi.mock('../../../services/newsApi', () => ({ fetchNews: () => Promise.resolve({ items: [] }) }))
vi.mock('../../../services/testimonialsApi', () => ({ fetchTestimonials: () => Promise.resolve({ items: [] }) }))
vi.mock('../../../services/sponsorsApi', () => ({ fetchSponsors: () => Promise.resolve([]) }))
const mockHomeContent = vi.fn()
vi.mock('../../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/siteContent')>()),
  loadHomeContent: () => mockHomeContent(),
}))

import { fillHomeContent } from '../../../services/siteContent'
import HomeView from '../HomeView.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }
const EVENT = { id: 1, title: 'Summer fest', slug: 'summer-fest', start_datetime: '2030-07-01T18:00:00', venue: 'Hall', published: true }

beforeEach(() => {
  vi.clearAllMocks()
  off.keys = []
  mockHomeContent.mockResolvedValue(fillHomeContent(undefined))
  mockEvents.mockResolvedValue({ items: [EVENT] })
})

describe('Home page and the Events module', () => {
  it('on: programme, Up next card and the programme button are there', async () => {
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(mockEvents).toHaveBeenCalled()
    expect(wrapper.text()).toContain("What's on this season")
    expect(wrapper.text()).toContain('See the programme')
    expect(wrapper.find('.ds-hero-stage-ribbon').exists()).toBe(true)
  })

  it('off: none of it, no request, no link to /events', async () => {
    off.keys = ['events']
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(mockEvents).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain("What's on this season")
    expect(wrapper.text()).not.toContain('See the programme')
    expect(wrapper.find('.ds-hero-stage-ribbon').exists()).toBe(false)
    expect(wrapper.find('a[href="/events"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain("Couldn't load events")
  })
})
