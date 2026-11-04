// Tests for HomeViewModules (5 cases), e.g. HomeView without the Testimonials module; shows no testimonial part and does not ask for testimonials; the assoc; HomeView without the Sponsors module (W8-R11).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Testimonials module (W8-R10): nothing of it on the home page, and its API is not even asked.
const off = vi.hoisted(() => ({ keys: ['testimonials'] as string[] }))
vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => !off.keys.includes(key ?? ''), offeredPhrase: () => '' }))

const mockFetchTestimonials = vi.fn()
vi.mock('../../../services/eventsApi', () => ({ fetchEvents: () => Promise.resolve({ items: [] }) }))
vi.mock('../../../services/galleryApi', () => ({ fetchAlbums: () => Promise.resolve({ items: [] }), fetchGalleryMedia: () => Promise.resolve([]) }))
vi.mock('../../../services/newsApi', () => ({ fetchNews: () => Promise.resolve({ items: [] }) }))
vi.mock('../../../services/testimonialsApi', () => ({ fetchTestimonials: (...args: unknown[]) => mockFetchTestimonials(...args) }))
const mockFetchSponsors = vi.fn()
vi.mock('../../../services/sponsorsApi', () => ({ fetchSponsors: (...args: unknown[]) => mockFetchSponsors(...args) }))

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
  off.keys = ['testimonials']
  mockFetchSponsors.mockResolvedValue([{ id: 1, name: 'Acme', logo_url: 'https://x/a.png', website_url: '' }])
  mockHomeContent.mockResolvedValue(
    fillHomeContent({ testimonials_eyebrow: 'What our members say', testimonials_empty_text: 'Be one of the first to share yours.', testimonials_button: 'Share your story', association_eyebrow: 'The association' }),
  )
})

describe('HomeView without the Testimonials module', () => {
  it('shows no testimonial part and does not ask for testimonials; the association part stays', async () => {
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchTestimonials).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('What our members say')
    expect(wrapper.text()).not.toContain('Be one of the first')
    expect(wrapper.find('a[href="/testimonials"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('The association')
  })
})

describe('HomeView without the Sponsors module (W8-R11)', () => {
  it('shows no sponsor strip and does not ask for sponsors', async () => {
    off.keys = ['sponsors']
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchSponsors).not.toHaveBeenCalled()
    expect(wrapper.find('.sponsors-marquee').exists()).toBe(false)
  })

  it('with the module on, the strip is asked for', async () => {
    off.keys = []
    mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchSponsors).toHaveBeenCalled()
  })
})
