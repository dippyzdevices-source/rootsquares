// Tests for MessagesUnsubscribeView (4 cases), e.g. MessagesUnsubscribeView; opts the address out when the link is opened and says that service mes; says the link is not valid for a wrong token.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

let query: Record<string, string> = {}
vi.mock('vue-router', () => ({ useRoute: () => ({ query }) }))
const unsubscribe = vi.fn()
vi.mock('../../../services/messagesApi', () => ({ unsubscribeFromMessages: (...a: unknown[]) => unsubscribe(...a) }))

import MessagesUnsubscribeView from '../MessagesUnsubscribeView.vue'

describe('MessagesUnsubscribeView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    query = { e: 'a@x.org', t: 'tok' }
  })

  it('opts the address out when the link is opened and says that service messages can still arrive', async () => {
    unsubscribe.mockResolvedValue(true)
    const wrapper = mount(MessagesUnsubscribeView)
    await flushPromises()
    expect(unsubscribe).toHaveBeenCalledWith('a@x.org', 'tok')
    expect(wrapper.find('.ds-alert-success').exists()).toBe(true)
    expect(wrapper.text()).toContain('Messages about things you booked')
  })

  it('says the link is not valid for a wrong token', async () => {
    unsubscribe.mockResolvedValue(false)
    const wrapper = mount(MessagesUnsubscribeView)
    await flushPromises()
    expect(wrapper.find('.ds-alert-danger').exists()).toBe(true)
  })

  it('does not call the server for a link without its parts', async () => {
    query = {}
    const wrapper = mount(MessagesUnsubscribeView)
    await flushPromises()
    expect(unsubscribe).not.toHaveBeenCalled()
    expect(wrapper.find('.ds-alert-danger').exists()).toBe(true)
  })
})
