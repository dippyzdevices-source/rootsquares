// Tests for FoundersOff (3 cases), e.g. About page and the Founders module; on: the founders are asked for and their quote is shown; off: no request and no founder part, the story text stays.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Founders module (W8-R13): the About page asks for no founders and shows none; the rest of the page stays.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => !off.keys.includes(key ?? '') }))
vi.mock('../../../services/settingsApi', () => ({ fetchSettings: () => Promise.resolve({ heritage_image_url: null, about_text: 'Our story.' }) }))
const mockFetchFounders = vi.fn()
vi.mock('../../../services/foundersApi', () => ({ fetchFounders: (...args: unknown[]) => mockFetchFounders(...args) }))
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
  off.keys = []
  mockHomeContent.mockResolvedValue(fillHomeContent(undefined))
  mockFetchFounders.mockResolvedValue([{ id: 1, name: 'A. Founder', sub_name: '', role: 'Founder', quote: 'We began small.', portrait_url: null, published: true }])
})

describe('About page and the Founders module', () => {
  it('on: the founders are asked for and their quote is shown', async () => {
    const wrapper = mount(HeritageView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchFounders).toHaveBeenCalled()
    expect(wrapper.text()).toContain('We began small.')
  })

  it('off: no request and no founder part, the story text stays', async () => {
    off.keys = ['founders']
    const wrapper = mount(HeritageView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchFounders).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('We began small.')
    expect(wrapper.text()).toContain('Our story.')
  })
})
