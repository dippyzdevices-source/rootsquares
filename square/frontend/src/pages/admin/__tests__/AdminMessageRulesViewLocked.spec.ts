// Tests for AdminMessageRulesViewLocked (2 cases), e.g. AdminMessageRulesView when the package has no reminders; names the package, keeps the list and disables the changes.
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square whose package has no automatic reminders (W14-R25): the list stays readable, nothing can be added, edited or turned on.
vi.mock('../../../services/features', () => ({ featureEnabled: () => false, GROVE_NOTE: 'Included in the Grove package.' }))
const rule = { id: 1, name: 'Day before', trigger: 'event_before', offset_days: 1, send_hour: 9, enabled: true, subject: 'Tomorrow', body_html: '<p>Hi</p>' }
vi.mock('../../../services/messagesApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/messagesApi')>()),
  fetchMessageOptions: () => Promise.resolve({ audiences: [], events: [], membership_types: [], membership_statuses: [], triggers: [{ key: 'event_before', label: 'Before an event', placeholders: [] }] }),
  fetchRules: () => Promise.resolve({ items: [rule] }),
}))
vi.mock('../../../components/ui/RichTextEditor.vue', () => ({ default: { template: '<div />' } }))

import AdminMessageRulesView from '../AdminMessageRulesView.vue'

describe('AdminMessageRulesView when the package has no reminders', () => {
  it('names the package, keeps the list and disables the changes', async () => {
    const wrapper = mount(AdminMessageRulesView)
    await flushPromises()
    expect(wrapper.find('.feature-locked').text()).toContain('Included in the Grove package.')
    expect(wrapper.find('.feature-locked').text()).toContain('Yours are kept but not sent.')
    expect(wrapper.text()).toContain('Day before')
    for (const sel of ['.new-rule', '.edit-rule', '.toggle-rule']) expect(wrapper.find(sel).attributes('disabled')).toBeDefined()
  })
})
