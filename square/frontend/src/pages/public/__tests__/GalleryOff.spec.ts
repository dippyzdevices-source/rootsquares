// Tests for GalleryOff (5 cases), e.g. Home page and the Gallery module; on: the gallery part is there and photos are asked for; off: no gallery part, no link to it, no request for albums or photos.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Gallery module (W8-R17): no gallery part and no photo carousel on the Home page, and no request for albums or photos.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/modules')>()),
  moduleEnabled: (key?: string) => !off.keys.includes(key ?? ''),
  offeredPhrase: () => '',
}))
const mockFetchAlbums = vi.fn()
const mockFetchMedia = vi.fn()
const mockEvents = vi.fn()
vi.mock('../../../services/eventsApi', () => ({ fetchEvents: (...a: unknown[]) => mockEvents(...a) }))
vi.mock('../../../services/galleryApi', () => ({ fetchAlbums: (...a: unknown[]) => mockFetchAlbums(...a), fetchGalleryMedia: (...a: unknown[]) => mockFetchMedia(...a) }))
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

beforeEach(() => {
  vi.clearAllMocks()
  off.keys = []
  mockHomeContent.mockResolvedValue(fillHomeContent(undefined))
  mockFetchAlbums.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
  mockFetchMedia.mockResolvedValue([])
  mockEvents.mockResolvedValue({ items: [] })
})

describe('Home page and the Gallery module', () => {
  it('on: the gallery part is there and photos are asked for', async () => {
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchAlbums).toHaveBeenCalled()
    expect(mockFetchMedia).toHaveBeenCalled()
    expect(wrapper.find('a[href="/gallery"]').exists()).toBe(true)
  })

  it('off: no gallery part, no link to it, no request for albums or photos', async () => {
    off.keys = ['gallery']
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchAlbums).not.toHaveBeenCalled()
    expect(mockFetchMedia).not.toHaveBeenCalled()
    expect(wrapper.find('a[href="/gallery"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Moments from')
  })

  it('off: no photo frame in the hero, but the Up next card of the Events module stays', async () => {
    off.keys = ['gallery']
    mockEvents.mockResolvedValue({ items: [{ id: 1, title: 'Summer fest', slug: 'summer-fest', start_datetime: '2030-07-01T18:00:00', venue: 'Hall', published: true }] })
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.ds-hero-stage-shot').exists()).toBe(false)
    expect(wrapper.find('.ds-hero-stage-ribbon').exists()).toBe(true)
    expect(wrapper.text()).toContain('Summer fest')
  })

  it('on: the photo frame is there (a placeholder until there are photos)', async () => {
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.ds-hero-stage-shot').exists()).toBe(true)
  })
})
