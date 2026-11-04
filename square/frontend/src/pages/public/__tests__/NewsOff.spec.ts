// Tests for NewsOff (3 cases), e.g. Home page and the News module; on: the news part is there and news is asked for; off: no news part, no request, and the intro does not name news.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the News module (W8-R16): no news part on the Home page and no request for news; the intro text follows what the square offers.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../services/modules')>()
  return { ...actual, moduleEnabled: (key?: string) => !off.keys.includes(key ?? ''), offeredPhrase: () => (off.keys.includes('news') ? 'events and tickets' : 'events, tickets and news') }
})
const mockFetchNews = vi.fn()
vi.mock('../../../services/eventsApi', () => ({ fetchEvents: () => Promise.resolve({ items: [] }) }))
vi.mock('../../../services/galleryApi', () => ({ fetchAlbums: () => Promise.resolve({ items: [] }), fetchGalleryMedia: () => Promise.resolve([]) }))
vi.mock('../../../services/newsApi', () => ({ fetchNews: (...args: unknown[]) => mockFetchNews(...args) }))
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
  mockFetchNews.mockResolvedValue({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 })
})

describe('Home page and the News module', () => {
  it('on: the news part is there and news is asked for', async () => {
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchNews).toHaveBeenCalled()
    expect(wrapper.text()).toContain('News & notices')
    expect(wrapper.text()).toContain('Events, tickets and news, all in one place.')
  })

  it('off: no news part, no request, and the intro does not name news', async () => {
    off.keys = ['news']
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchNews).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('News & notices')
    expect(wrapper.find('a[href="/news"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Events and tickets, all in one place.')
  })
})
