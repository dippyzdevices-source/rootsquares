// Tests for AdminMessageRulesView (4 cases), e.g. AdminMessageRulesView; lists the reminders with their timing and turns one off; creates a reminder and shows the placeholders the trigger allows.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const api = { fetchMessageOptions: vi.fn(), fetchRules: vi.fn(), createRule: vi.fn(), updateRule: vi.fn(), deleteRule: vi.fn() }
vi.mock('../../../services/messagesApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/messagesApi')>()),
  fetchMessageOptions: (...a: unknown[]) => api.fetchMessageOptions(...a),
  fetchRules: (...a: unknown[]) => api.fetchRules(...a),
  createRule: (...a: unknown[]) => api.createRule(...a),
  updateRule: (...a: unknown[]) => api.updateRule(...a),
  deleteRule: (...a: unknown[]) => api.deleteRule(...a),
}))
vi.mock('../../../components/ui/RichTextEditor.vue', () => ({
  default: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<textarea class="rte" :value="modelValue" @input="$emit(`update:modelValue`, $event.target.value)" />',
  },
}))

import AdminMessageRulesView from '../AdminMessageRulesView.vue'

const triggers = [{ key: 'event_before', label: 'Before an event, to its ticket holders', placeholders: ['name', 'event_title'] }]
const rule = { id: 1, name: 'Day before', trigger: 'event_before', offset_days: 1, send_hour: 9, enabled: true, subject: 'Tomorrow', body_html: '<p>Hi</p>' }
let wrapper: ReturnType<typeof mount> | null = null

function type(selector: string, value: string) {
  const el = document.body.querySelector(selector) as HTMLInputElement | HTMLTextAreaElement
  el.value = value
  el.dispatchEvent(new Event('input'))
}

beforeEach(() => {
  vi.clearAllMocks()
  api.fetchMessageOptions.mockResolvedValue({ audiences: [], events: [], membership_types: [], membership_statuses: [], triggers })
  api.fetchRules.mockResolvedValue({ items: [rule] })
})
afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
})

describe('AdminMessageRulesView', () => {
  it('lists the reminders with their timing and turns one off', async () => {
    api.updateRule.mockResolvedValue({ ...rule, enabled: false })
    wrapper = mount(AdminMessageRulesView, { attachTo: document.body })
    await flushPromises()
    expect(wrapper.text()).toContain('Day before')
    expect(wrapper.text()).toContain('1 day before, at 09:00')
    await wrapper.find('.toggle-rule').trigger('click')
    await flushPromises()
    expect(api.updateRule).toHaveBeenCalledWith(1, { enabled: false })
  })

  it('creates a reminder and shows the placeholders the trigger allows', async () => {
    api.createRule.mockResolvedValue(rule)
    wrapper = mount(AdminMessageRulesView, { attachTo: document.body })
    await flushPromises()
    await wrapper.find('.new-rule').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('{{event_title}}')
    type('.rule-name', 'Day before')
    type('.rule-subject', 'Soon')
    type('.rte', '<p>Hi</p>')
    ;(document.body.querySelector('.save-rule') as HTMLElement).click()
    await flushPromises()
    expect(api.createRule).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Day before', trigger: 'event_before', offset_days: 1, send_hour: 9, subject: 'Soon' }),
    )
  })
  it('offers the suggested reminders to a square with none, only those whose trigger is available, and makes them when asked', async () => {
    api.fetchRules.mockResolvedValueOnce({ items: [] }).mockResolvedValue({ items: [rule] })
    api.createRule.mockResolvedValue(rule)
    wrapper = mount(AdminMessageRulesView, { attachTo: document.body })
    await flushPromises()
    expect(wrapper.find('.suggested-reminders').exists()).toBe(true)
    expect(wrapper.find('.suggested-reminders').text()).toContain('The day before an event')
    expect(wrapper.find('.suggested-reminders').text()).not.toContain('membership ends') // its trigger is not available here
    await wrapper.find('.add-suggested').trigger('click')
    await flushPromises()
    expect(api.createRule).toHaveBeenCalledTimes(1)
    expect(api.createRule).toHaveBeenCalledWith(expect.objectContaining({ trigger: 'event_before', offset_days: 1, send_hour: 9 }))
    expect(wrapper.find('.suggested-reminders').exists()).toBe(false) // there are reminders now
  })
})
