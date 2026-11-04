// Tests for NewsletterOff (3 cases), e.g. News page and the Newsletter module; on: the sign-up band shows; off: no band and no sign-up form.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Newsletter module (W8-R15): no sign-up band on the News page, even if its words are set.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => !off.keys.includes(key ?? '') }))
vi.mock('../../../services/lookupsApi', () => ({ fetchLookup: vi.fn().mockResolvedValue([]) }))
vi.mock('../../../services/newsApi', () => ({ fetchNews: () => Promise.resolve({ items: [], page: 1, per_page: 7, total: 0, total_pages: 0 }) }))
vi.mock('../../../services/newsletterApi', () => ({ subscribeNewsletter: vi.fn() }))
const mockHomeContent = vi.fn()
vi.mock('../../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/siteContent')>()),
  loadHomeContent: () => mockHomeContent(),
}))

import { fillHomeContent } from '../../../services/siteContent'
import NewsListView from '../NewsListView.vue'

beforeEach(() => {
  off.keys = []
  mockHomeContent.mockResolvedValue(fillHomeContent({ news_band: { eyebrow: '', title: 'The newsletter', text: 'Now and then.', consent: '', show_magazines: false } }))
})

describe('News page and the Newsletter module', () => {
  it('on: the sign-up band shows', async () => {
    const wrapper = mount(NewsListView)
    await flushPromises()
    expect(wrapper.find('form input[type="email"]').exists()).toBe(true)
  })

  it('off: no band and no sign-up form', async () => {
    off.keys = ['newsletter']
    const wrapper = mount(NewsListView)
    await flushPromises()
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('The newsletter')
  })
})
