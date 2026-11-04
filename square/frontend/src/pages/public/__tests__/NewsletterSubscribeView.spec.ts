// Tests for NewsletterSubscribeView (2 cases), e.g. NewsletterSubscribeView (a square with the newsletter and no news); shows the square\.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const subscribe = vi.fn()
vi.mock('../../../services/newsletterApi', () => ({ subscribeNewsletter: (...a: unknown[]) => subscribe(...a) }))
vi.mock('../../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/siteContent')>()),
  loadHomeContent: async () => ({ news_band: { eyebrow: 'Stay in touch', title: 'Our letter', text: 'Once a month.', consent: 'You can leave any time.', show_magazines: false } }),
}))

import NewsletterSubscribeView from '../NewsletterSubscribeView.vue'

beforeEach(() => vi.clearAllMocks())

describe('NewsletterSubscribeView (a square with the newsletter and no news)', () => {
  it('shows the square\'s own words and subscribes an address', async () => {
    subscribe.mockResolvedValue(undefined)
    const wrapper = mount(NewsletterSubscribeView)
    await flushPromises()
    expect(wrapper.text()).toContain('Our letter')
    expect(wrapper.text()).toContain('You can leave any time.')
    await wrapper.find('input[type=email]').setValue(' me@example.com ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(subscribe).toHaveBeenCalledWith('me@example.com')
    expect(wrapper.find('.newsletter-done').exists()).toBe(true)
  })
})
