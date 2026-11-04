// Tests for HeritageView (7 cases), e.g. HeritageView; shows the square's own name and its hero photo when an admin set one; reads fine without a photo or when the settings cannot be loaded, and.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchSettings = vi.fn()
vi.mock('../../../services/settingsApi', () => ({ fetchSettings: () => mockFetchSettings() }))

const mockFetchFounders = vi.fn()
vi.mock('../../../services/foundersApi', () => ({ fetchFounders: () => mockFetchFounders() }))
const mockHomeContent = vi.fn()
vi.mock('../../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/siteContent')>()),
  loadHomeContent: () => mockHomeContent(),
}))

import { fillHomeContent } from '../../../services/siteContent'
import HeritageView from '../HeritageView.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchFounders.mockResolvedValue([])
  mockHomeContent.mockResolvedValue(fillHomeContent(undefined))
})

// bca-oslo's own story (history, timeline, founders, festivals) was removed (rootsquares W6-R41).
describe('HeritageView', () => {
  it("shows the square's own name and its hero photo when an admin set one", async () => {
    mockFetchSettings.mockResolvedValue({ heritage_image_url: 'https://x/group.jpg' })
    const wrapper = mount(HeritageView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('About')
    expect(wrapper.find('img').attributes('src')).toBe('https://x/group.jpg')
  })

  it('reads fine without a photo or when the settings cannot be loaded, and carries nothing of bca-oslo', async () => {
    mockFetchSettings.mockRejectedValue(new Error('offline'))
    const wrapper = mount(HeritageView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('img').exists()).toBe(false)
    for (const word of ['Bengal', 'Durga', 'Norway', 'Sanatan']) // (the test fallback name is 'BCA Oslo', so not 'Oslo')
      expect(wrapper.text()).not.toContain(word)
  })
  it("shows the square's own About text when it has one (W6-R58)", async () => {
    mockFetchSettings.mockResolvedValue({ about_text: 'We began in a living room.' })
    const wrapper = mount(HeritageView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.get('[data-testid=about-text]').text()).toBe('We began in a living room.')
    expect(wrapper.text()).not.toContain('has not added its story')
  })

  it('shows no extra sections until the square sets them (W7-R10)', async () => {
    mockFetchSettings.mockResolvedValue({ about_text: 'We began in a living room.' })
    const wrapper = mount(HeritageView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.findAll('section')).toHaveLength(2) // the hero and the About text
    expect(wrapper.find('a[href="/committee"]').exists()).toBe(false)
  })

  it("shows the square's own cards, what-we-do text, timeline and get-involved card", async () => {
    mockFetchSettings.mockResolvedValue({})
    mockHomeContent.mockResolvedValue(
      fillHomeContent({
        about_page: {
          values_title: 'Who are we',
          values_button: 'Meet the committee',
          values: [{ title: 'Community first', description: 'Together.' }],
          what_title: 'What we do',
          what_text: 'Events all year.',
          what_membership_link: 'Membership',
          what_events_link: '',
          timeline_eyebrow: 'Timeline',
          timeline_title: 'How it happened',
          timeline: [{ year: '2010', title: 'We began', description: '' }],
          involve_badge: 'Get involved',
          involve_title: 'Join us',
          involve_text: 'Volunteers welcome.',
          involve_button: 'Get in touch',
        },
      }),
    )
    const wrapper = mount(HeritageView, { global: { stubs } })
    await flushPromises()
    for (const text of ['Who are we', 'Community first', 'Together.', 'What we do', 'Events all year.', 'How it happened', '2010', 'We began', 'Join us', 'Volunteers welcome.'])
      expect(wrapper.text()).toContain(text)
    expect(wrapper.find('a[href="/committee"]').text()).toBe('Meet the committee')
    expect(wrapper.find('a[href="/membership"]').text()).toBe('Membership')
    expect(wrapper.find('a[href="/events"]').exists()).toBe(false) // no link text = no link
    expect(wrapper.find('a[href="/contact"]').text()).toBe('Get in touch')
  })

  it("shows the founders' quotes when the square has founders, with next and previous buttons for more than one", async () => {
    mockFetchSettings.mockResolvedValue({})
    mockFetchFounders.mockResolvedValue([
      { id: 1, name: 'Anna', sub_name: null, role: 'Founder', quote: 'Start small.', portrait_url: null },
      { id: 2, name: 'Ben', sub_name: null, role: 'Founder', quote: 'Keep going.', portrait_url: null },
    ])
    const wrapper = mount(HeritageView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Start small.')
    await wrapper.get('button[aria-label="Next founder quote"]').trigger('click')
    expect(wrapper.text()).toContain('Keep going.')
    wrapper.unmount()
  })
})
