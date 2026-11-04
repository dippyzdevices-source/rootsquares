// Tests for NewsletterUnsubscribeView (3 cases), e.g. NewsletterUnsubscribeView; unsubscribes with the token from the link; shows an invalid-link message with no token or an unknown token.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockUnsubscribe = vi.fn()
let query: Record<string, string> = {}

vi.mock('../../../services/newsletterApi', () => ({
  unsubscribeNewsletter: (...args: unknown[]) => mockUnsubscribe(...args),
}))
vi.mock('vue-router', () => ({ useRoute: () => ({ query }) }))

import NewsletterUnsubscribeView from '../NewsletterUnsubscribeView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  query = {}
})

describe('NewsletterUnsubscribeView', () => {
  it('unsubscribes with the token from the link', async () => {
    query = { token: 'abc' }
    mockUnsubscribe.mockResolvedValue(true)
    const wrapper = mount(NewsletterUnsubscribeView)
    await flushPromises()
    expect(mockUnsubscribe).toHaveBeenCalledWith('abc')
    expect(wrapper.text()).toContain("You're unsubscribed")
  })

  it('shows an invalid-link message with no token or an unknown token', async () => {
    const noToken = mount(NewsletterUnsubscribeView)
    await flushPromises()
    expect(noToken.text()).toContain("isn't valid")
    expect(mockUnsubscribe).not.toHaveBeenCalled()

    query = { token: 'nope' }
    mockUnsubscribe.mockResolvedValue(false)
    const unknown = mount(NewsletterUnsubscribeView)
    await flushPromises()
    expect(unknown.text()).toContain("isn't valid")
  })
})
