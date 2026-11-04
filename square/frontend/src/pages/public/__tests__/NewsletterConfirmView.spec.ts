// Tests for NewsletterConfirmView (3 cases), e.g. NewsletterConfirmView; confirms with the token from the link; shows an invalid-link message with no token or an unknown token.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockConfirm = vi.fn()
let query: Record<string, string> = {}

vi.mock('../../../services/newsletterApi', () => ({
  confirmNewsletter: (...args: unknown[]) => mockConfirm(...args),
}))
vi.mock('vue-router', () => ({ useRoute: () => ({ query }) }))

import NewsletterConfirmView from '../NewsletterConfirmView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  query = {}
})

describe('NewsletterConfirmView', () => {
  it('confirms with the token from the link', async () => {
    query = { token: 'abc' }
    mockConfirm.mockResolvedValue(true)
    const wrapper = mount(NewsletterConfirmView)
    await flushPromises()
    expect(mockConfirm).toHaveBeenCalledWith('abc')
    expect(wrapper.text()).toContain("You're subscribed")
  })

  it('shows an invalid-link message with no token or an unknown token', async () => {
    const noToken = mount(NewsletterConfirmView)
    await flushPromises()
    expect(noToken.text()).toContain("isn't valid")
    expect(mockConfirm).not.toHaveBeenCalled()

    query = { token: 'nope' }
    mockConfirm.mockResolvedValue(false)
    const unknown = mount(NewsletterConfirmView)
    await flushPromises()
    expect(unknown.text()).toContain("isn't valid")
  })
})
