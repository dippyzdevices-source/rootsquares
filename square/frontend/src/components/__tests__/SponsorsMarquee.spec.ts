// Tests for SponsorsMarquee (5 cases), e.g. SponsorsMarquee; renders nothing when there are no sponsors; renders nothing when the fetch fails.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchSponsors = vi.fn()
vi.mock('../../services/sponsorsApi', () => ({
  fetchSponsors: (...args: unknown[]) => mockFetchSponsors(...args),
}))

const mockHomeContent = vi.fn()
vi.mock('../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/siteContent')>()),
  loadHomeContent: () => mockHomeContent(),
}))

import { fillHomeContent } from '../../services/siteContent'
import SponsorsMarquee from '../SponsorsMarquee.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mockHomeContent.mockResolvedValue(fillHomeContent(undefined))
})

describe('SponsorsMarquee', () => {
  it('renders nothing when there are no sponsors', async () => {
    mockFetchSponsors.mockResolvedValue([])
    const wrapper = mount(SponsorsMarquee)
    await flushPromises()
    expect(wrapper.find('section').exists()).toBe(false)
  })

  it('renders nothing when the fetch fails', async () => {
    mockFetchSponsors.mockRejectedValue(new Error('boom'))
    const wrapper = mount(SponsorsMarquee)
    await flushPromises()
    expect(wrapper.find('section').exists()).toBe(false)
  })

  it('repeats a short list into two identical laps, links out, and hides the copy from assistive tech', async () => {
    mockFetchSponsors.mockResolvedValue([
      { id: 1, name: 'Acme', logo_url: 'https://cdn/acme.webp', website_url: 'https://acme.no' },
      { id: 2, name: 'NoSite', logo_url: null, website_url: null },
    ])
    const wrapper = mount(SponsorsMarquee)
    await flushPromises()

    const items = wrapper.findAll('li')
    // 2 sponsors -> lap of 8 -> track of 16
    expect(items).toHaveLength(16)
    expect(items.filter((li) => li.attributes('aria-hidden') === 'true')).toHaveLength(8)
    const link = wrapper.find('a')
    expect(link.attributes('href')).toBe('https://acme.no')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
    expect(wrapper.find('img').attributes('alt')).toBe('Acme')
    expect(wrapper.text()).toContain('NoSite')
  })

  it("shows the square's own words above the strip, and no heading when none are set (W7-R6)", async () => {
    mockFetchSponsors.mockResolvedValue([{ id: 1, name: 'Acme', logo_url: null, website_url: null }])
    let wrapper = mount(SponsorsMarquee)
    await flushPromises()
    expect(wrapper.find('section').exists()).toBe(true)
    expect(wrapper.find('.ds-heading').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('With thanks to')

    mockHomeContent.mockResolvedValue(fillHomeContent({ sponsors_eyebrow: 'Friends', sponsors_title: 'Thank you' }))
    wrapper = mount(SponsorsMarquee)
    await flushPromises()
    expect(wrapper.find('.ds-eyebrow').text()).toBe('Friends')
    expect(wrapper.find('h2').text()).toBe('Thank you')
  })
})
