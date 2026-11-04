// Tests for AdminNewsletterIssuesView (4 cases), e.g. AdminNewsletterIssuesView; lists the messages sent to the subscribers, with delivery counts; opens a newsletter in the Messages editor.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchMessages = vi.fn()
const push = vi.fn()
vi.mock('../../../services/messagesApi', () => ({ fetchMessages: (...a: unknown[]) => mockFetchMessages(...a) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('../../../services/modules', () => ({ moduleEnabled: () => true }))

import AdminNewsletterIssuesView from '../AdminNewsletterIssuesView.vue'

const sent = {
  id: 3, kind: 'update', channel: 'email', subject: 'September news', body_html: '<p>x</p>', audience: { type: 'subscribers', params: {} },
  status: 'sent', source: 'manual', recipients_total: 4, sent_count: 3, failed_count: 0, skipped_count: 1,
  scheduled_for: null, sent_at: '2026-09-01T10:00:00Z', created_at: '2026-09-01T09:00:00Z',
}
const stubs = { RouterLink: { template: '<a><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AdminNewsletterIssuesView', () => {
  it('lists the messages sent to the subscribers, with delivery counts', async () => {
    mockFetchMessages.mockResolvedValue({ items: [sent], total: 1, page: 1, per_page: 25 })
    const wrapper = mount(AdminNewsletterIssuesView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchMessages).toHaveBeenCalledWith(1, 'subscribers')
    expect(wrapper.text()).toContain('September news')
    expect(wrapper.text()).toContain('3 / 3')
  })

  it('opens a newsletter in the Messages editor', async () => {
    mockFetchMessages.mockResolvedValue({ items: [sent], total: 1, page: 1, per_page: 25 })
    const wrapper = mount(AdminNewsletterIssuesView, { global: { stubs } })
    await flushPromises()
    await wrapper.find('tbody tr').trigger('click')
    expect(push).toHaveBeenCalledWith('/admin/messages/3')
  })

  it('says so when there are none', async () => {
    mockFetchMessages.mockResolvedValue({ items: [], total: 0, page: 1, per_page: 25 })
    const wrapper = mount(AdminNewsletterIssuesView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('No newsletters yet')
  })
})
