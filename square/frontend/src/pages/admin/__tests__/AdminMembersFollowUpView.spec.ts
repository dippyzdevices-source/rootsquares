// Tests for AdminMembersFollowUpView (7 cases), e.g. AdminMembersFollowUpView; lists unpaid requests and active members with dues, with what each owe; shows an empty state in each group.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchFollowUp = vi.fn()
const mockSendReminder = vi.fn()
const mockRemoveRequest = vi.fn()

vi.mock('../../../services/adminMembershipFollowUpApi', () => ({
  fetchFollowUp: (...a: unknown[]) => mockFetchFollowUp(...a),
  sendFollowUpReminder: (...a: unknown[]) => mockSendReminder(...a),
  removeFollowUpRequest: (...a: unknown[]) => mockRemoveRequest(...a),
}))

import AdminMembersFollowUpView from '../AdminMembersFollowUpView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }
let wrapper: ReturnType<typeof mount> | null = null

const request = (over = {}) => ({
  membership_id: 7, member_id: 1, name: 'Priya Das', email: 'priya@example.com', phone: '41234567',
  membership_type: 'adult', period_label: 'October 2026', amount: 30000, requested_at: '2026-10-01T10:00:00+00:00',
  days_waiting: 5, last_reminded_at: null, can_remind: true, ...over,
})
const due = (over = {}) => ({
  membership_id: 8, member_id: 2, name: 'Rohan Das', email: 'rohan@example.com', phone: null,
  membership_type: 'adult', due_count: 3, due_total: 90000, due_labels: ['August 2026', 'September 2026', 'October 2026'],
  days_overdue: 60, last_reminded_at: null, can_remind: true, ...over,
})

async function mountView(data = { requests: [request()], dues: [due()] }) {
  mockFetchFollowUp.mockResolvedValue(data)
  wrapper = mount(AdminMembersFollowUpView, { global: { stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => vi.clearAllMocks())
afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('AdminMembersFollowUpView', () => {
  it('lists unpaid requests and active members with dues, with what each owes', async () => {
    const w = await mountView()

    const req = w.find('.followup-request-row')
    expect(req.text()).toContain('Priya Das')
    expect(req.text()).toContain('October 2026')
    expect(req.text()).toContain('5 days')
    expect(req.text()).toContain('Never')

    const row = w.find('.followup-due-row')
    expect(row.text()).toContain('Rohan Das')
    expect(row.text()).toContain('3 periods')
    expect(row.text()).toContain('60 days')
    expect(row.find('.remove-request').exists()).toBe(false) // active members are never removed from here
  })

  it('shows an empty state in each group', async () => {
    const w = await mountView({ requests: [], dues: [] })
    expect(w.text()).toContain('No unpaid requests')
    expect(w.text()).toContain('Nothing overdue')
  })

  it('sends a reminder, then disables the button for the cooldown', async () => {
    mockSendReminder.mockResolvedValue({ last_reminded_at: new Date().toISOString() })
    const w = await mountView({ requests: [request()], dues: [] })

    const button = w.find('.send-reminder')
    expect((button.element as HTMLButtonElement).disabled).toBe(false)
    await button.trigger('click')
    await flushPromises()

    expect(mockSendReminder).toHaveBeenCalledWith(7)
    expect((w.find('.send-reminder').element as HTMLButtonElement).disabled).toBe(true)
    expect(w.find('.followup-request-row').text()).toContain('Today')
  })

  it('disables Remind inside the cooldown or when the member has no email', async () => {
    const w = await mountView({
      requests: [request({ can_remind: false, last_reminded_at: '2026-10-05T10:00:00+00:00' })],
      dues: [due({ email: null })],
    })
    for (const button of w.findAll('.send-reminder')) {
      expect((button.element as HTMLButtonElement).disabled).toBe(true)
    }
  })

  it('removes a stale request only after confirming', async () => {
    mockRemoveRequest.mockResolvedValue(undefined)
    const w = await mountView({ requests: [request()], dues: [] })

    await w.find('.remove-request').trigger('click')
    expect(mockRemoveRequest).not.toHaveBeenCalled()
    await new DOMWrapper(document.body).find('.confirm-remove').trigger('click')
    await flushPromises()

    expect(mockRemoveRequest).toHaveBeenCalledWith(7)
    expect(w.find('.followup-request-row').exists()).toBe(false)
  })

  it('shows an error state when the list cannot be loaded', async () => {
    mockFetchFollowUp.mockRejectedValue(new Error('x'))
    wrapper = mount(AdminMembersFollowUpView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain("Couldn't load this list")
  })
})
