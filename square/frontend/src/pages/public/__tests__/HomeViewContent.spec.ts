// Tests for HomeViewContent (3 cases), e.g. HomeView: the square's own words (W6-R64); shows neutral text when the square has set nothing; shows the headline, handwritten line, own-language line, introduction,.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockLoadHomeContent = vi.fn()

vi.mock('../../../services/siteContent', async () => {
  const actual = await vi.importActual<typeof import('../../../services/siteContent')>('../../../services/siteContent')
  return { ...actual, loadHomeContent: () => mockLoadHomeContent() }
})
vi.mock('../../../services/eventsApi', () => ({ fetchEvents: () => Promise.resolve({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 }) }))
vi.mock('../../../services/galleryApi', () => ({
  fetchAlbums: () => Promise.resolve({ items: [], page: 1, per_page: 3, total: 0, total_pages: 0 }),
  fetchGalleryMedia: () => Promise.resolve([]),
}))
vi.mock('../../../services/newsApi', () => ({ fetchNews: () => Promise.resolve({ items: [], page: 1, per_page: 2, total: 0, total_pages: 0 }) }))
vi.mock('../../../services/testimonialsApi', () => ({ fetchTestimonials: () => Promise.resolve({ items: [] }) }))
vi.mock('../../../services/sponsorsApi', () => ({ fetchSponsors: () => Promise.resolve([]) }))

import HomeView from '../HomeView.vue'
import { EMPTY_HOME_CONTENT } from '../../../services/siteContent'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => vi.clearAllMocks())

describe("HomeView: the square's own words (W6-R64)", () => {
  it('shows neutral text when the square has set nothing', async () => {
    mockLoadHomeContent.mockResolvedValue({ ...EMPTY_HOME_CONTENT })
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Welcome')
    expect(wrapper.text()).toContain('Events, tickets, membership and news, all in one place.')
    expect(wrapper.find('.ds-script').exists()).toBe(false)
  })

  it('shows the headline, handwritten line, own-language line, introduction, name, numbers and band text it has set', async () => {
    mockLoadHomeContent.mockResolvedValue({
      ...EMPTY_HOME_CONTENT,
      eyebrow: 'Community · culture',
      script_line: 'since 2010',
      headline: 'Bengal, kept alive in Oslo',
      local_line: 'অসলোয় বাংলার প্রাণ',
      intro: 'Durga Puja in a rented hall.',
      intro_name: 'Bengali Cultural Association',
      intro_suffix: 'of Oslo.',
      stats: [{ value: '16', label: 'years in Oslo' }],
      blurb: 'We bring the community together.',
    })
    const wrapper = mount(HomeView, { global: { stubs } })
    await flushPromises()
    const text = wrapper.text()
    for (const part of ['Community · culture', 'since 2010', 'Bengal, kept alive in Oslo', 'অসলোয় বাংলার প্রাণ', 'Durga Puja in a rented hall.', 'Bengali Cultural Association', 'of Oslo.', '16', 'years in Oslo', 'We bring the community together.']) {
      expect(text).toContain(part)
    }
    expect(text).not.toContain('Events, tickets, membership and news')
  })
})
