// Tests for AdminMessageFormView (6 cases), e.g. AdminMessageFormView; presets the audience from the link of the Newsletters tab; shows how many people the audience reaches and how many opted out.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { chooseOption } from '../../../test-utils/baseSelect'

const api = {
  fetchMessageOptions: vi.fn(),
  previewAudience: vi.fn(),
  createMessage: vi.fn(),
  updateMessage: vi.fn(),
  sendMessage: vi.fn(),
  sendTestMessage: vi.fn(),
  fetchMessage: vi.fn(),
  fetchMessageRecipients: vi.fn(),
}
vi.mock('../../../services/messagesApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/messagesApi')>()),
  fetchMessageOptions: (...a: unknown[]) => api.fetchMessageOptions(...a),
  previewAudience: (...a: unknown[]) => api.previewAudience(...a),
  createMessage: (...a: unknown[]) => api.createMessage(...a),
  updateMessage: (...a: unknown[]) => api.updateMessage(...a),
  sendMessage: (...a: unknown[]) => api.sendMessage(...a),
  sendTestMessage: (...a: unknown[]) => api.sendTestMessage(...a),
  fetchMessage: (...a: unknown[]) => api.fetchMessage(...a),
  fetchMessageRecipients: (...a: unknown[]) => api.fetchMessageRecipients(...a),
  deleteMessage: vi.fn(),
  unscheduleMessage: vi.fn(),
}))
let params: Record<string, string> = {}
let query: Record<string, string> = {}
const replace = vi.fn()
vi.mock('vue-router', () => ({ useRoute: () => ({ params, query }), useRouter: () => ({ push: vi.fn(), replace }) }))
vi.mock('../../../components/ui/RichTextEditor.vue', () => ({
  default: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<textarea class="rte" :value="modelValue" @input="$emit(`update:modelValue`, $event.target.value)" />',
  },
}))

// W26-R18: the square's own sending domain is verified or not (the tests flip it on the real profile); a newsletter is held back until it is
import { squareProfile as profile } from '../../../services/squareConfig'

import AdminMessageFormView from '../AdminMessageFormView.vue'

const options = {
  audiences: [
    { key: 'members', label: 'Members and people', description: 'Everyone on the member list.', params: [] },
    { key: 'subscribers', label: 'Newsletter subscribers', description: 'People who subscribed.', params: [] },
    { key: 'ticket_holders', label: 'Ticket holders of an event', description: 'Paid orders.', params: [{ name: 'event_id', label: 'Event', type: 'event', required: true }] },
  ],
  events: [{ id: 7, title: 'Spring Gala', start: '2026-12-01T18:00:00Z' }],
  membership_types: [],
  membership_statuses: [],
  triggers: [],
}
const draft = {
  id: 3, kind: 'update', channel: 'email', subject: 'Hello', body_html: '<p>x</p>', audience: { type: 'members', params: {} },
  status: 'draft', source: 'manual', recipients_total: 0, sent_count: 0, failed_count: 0, skipped_count: 0,
  scheduled_for: null, sent_at: null, created_at: '2026-10-14T10:00:00Z',
}
let wrapper: ReturnType<typeof mount> | null = null

beforeEach(() => {
  vi.clearAllMocks()
  params = {}
  query = {}
  api.fetchMessageOptions.mockResolvedValue(options)
  api.previewAudience.mockResolvedValue({ total: 12, skipped: 2, will_receive: 10 })
})
afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
})

describe('AdminMessageFormView', () => {
  it('holds a newsletter back, with the reason, until the own sending domain is verified (W26-R18)', async () => {
    query = { audience: 'subscribers' }
    profile.ownMailDomain = false
    wrapper = mount(AdminMessageFormView, { attachTo: document.body })
    await flushPromises()
    expect(wrapper.find('.newsletter-blocked').text()).toContain('own sending domain')
    expect((wrapper.find('.open-send').element as HTMLButtonElement).disabled).toBe(true)
    profile.ownMailDomain = true
  })

  it('does not hold back a newsletter when the own sending domain is verified, or any other message', async () => {
    query = { audience: 'subscribers' }
    profile.ownMailDomain = true
    wrapper = mount(AdminMessageFormView, { attachTo: document.body })
    await flushPromises()
    expect(wrapper.find('.newsletter-blocked').exists()).toBe(false)
    profile.ownMailDomain = false
    query = {}
    wrapper.unmount()
    wrapper = mount(AdminMessageFormView, { attachTo: document.body })
    await flushPromises()
    expect(wrapper.find('.newsletter-blocked').exists()).toBe(false) // the default audience is members
    profile.ownMailDomain = true
  })

  it('presets the audience from the link of the Newsletters tab', async () => {
    query = { audience: 'subscribers' }
    api.createMessage.mockResolvedValue({ ...draft, audience: { type: 'subscribers', params: {} } })
    wrapper = mount(AdminMessageFormView, { attachTo: document.body })
    await flushPromises()
    await wrapper.find('.message-subject').setValue('Autumn news')
    await wrapper.find('.rte').setValue('<p>x</p>')
    await wrapper.find('.save-message').trigger('click')
    await flushPromises()
    expect(api.createMessage).toHaveBeenCalledWith(expect.objectContaining({ audience: { type: 'subscribers', params: {} } }))
  })

  it('shows how many people the audience reaches and how many opted out', async () => {
    wrapper = mount(AdminMessageFormView, { attachTo: document.body })
    await flushPromises()
    await new Promise((r) => setTimeout(r, 350))
    await flushPromises()
    expect(wrapper.find('.audience-preview').text()).toContain('10')
    expect(wrapper.find('.audience-preview').text()).toContain('2 opted out')
  })

  it('asks for an event when the audience needs one, and sends its id', async () => {
    api.createMessage.mockResolvedValue({ ...draft, audience: { type: 'ticket_holders', params: { event_id: 7 } } })
    wrapper = mount(AdminMessageFormView, { attachTo: document.body })
    await flushPromises()
    await chooseOption(wrapper, 'ticket_holders', 0)
    await flushPromises()
    await chooseOption(wrapper, '7', 1)
    await wrapper.find('.message-subject').setValue('Hello')
    await wrapper.find('.rte').setValue('<p>x</p>')
    await wrapper.find('.save-message').trigger('click')
    await flushPromises()
    expect(api.createMessage).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'update', subject: 'Hello', audience: { type: 'ticket_holders', params: { event_id: 7 } } }),
    )
  })

  it('saves, then confirms with the people count before sending now', async () => {
    api.createMessage.mockResolvedValue(draft)
    api.sendMessage.mockResolvedValue({ ...draft, status: 'sending', recipients_total: 12, skipped_count: 2 })
    api.fetchMessageRecipients.mockResolvedValue({ items: [], total: 0, page: 1, per_page: 50 })
    wrapper = mount(AdminMessageFormView, { attachTo: document.body })
    await flushPromises()
    await wrapper.find('.message-subject').setValue('Hello')
    await wrapper.find('.open-send').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('It goes to')
    ;(document.body.querySelector('.confirm-send') as HTMLElement).click()
    await flushPromises()
    expect(api.sendMessage).toHaveBeenCalledWith(3, undefined)
  })

  it('shows progress and the people list, read-only, for a message that was sent', async () => {
    params = { id: '3' }
    api.fetchMessage.mockResolvedValue({ ...draft, status: 'sent', recipients_total: 12, sent_count: 9, failed_count: 1, skipped_count: 2 })
    api.fetchMessageRecipients.mockResolvedValue({ items: [{ id: 1, email: 'a@x.org', name: 'Asha', status: 'sent' }], total: 1, page: 1, per_page: 50 })
    wrapper = mount(AdminMessageFormView, { attachTo: document.body })
    await flushPromises()
    expect(wrapper.text()).toContain('9')
    expect(wrapper.text()).toContain('skipped (opted out)')
    expect(wrapper.text()).toContain('a@x.org')
    expect(wrapper.find('.save-message').exists()).toBe(false)
    expect(wrapper.find('fieldset').attributes('disabled')).toBeDefined()
  })
})
