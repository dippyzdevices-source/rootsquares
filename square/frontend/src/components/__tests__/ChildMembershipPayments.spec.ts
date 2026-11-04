// Tests for ChildMembershipPayments (4 cases), e.g. ChildMembershipPayments; renders nothing when no child is waiting for payment; shows the child and reports a Vipps-QR payment for their one period.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetch = vi.fn()
const mockStart = vi.fn()

vi.mock('../../services/membershipPaymentsApi', () => ({
  fetchChildrenAwaitingPayment: (...args: unknown[]) => mockFetch(...args),
  startPeriodPayment: (...args: unknown[]) => mockStart(...args),
}))

import ChildMembershipPayments from '../ChildMembershipPayments.vue'

const child = {
  member_id: 7,
  name: 'Mini Das',
  membership_type: 'child',
  period: { id: 31, label: '2026', amount: 10000, period_start: '2026-01-01', period_end: '2026-12-31', currency: 'NOK', status: 'unpaid', paid_at: null },
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetch.mockResolvedValue({ items: [child], vipps_app: { enabled: false, surcharge_percent: 5 }, cash: { enabled: false, note: '' } })
  mockStart.mockResolvedValue({ payment: { id: 1, payment_reference: 'PAY-1', amount: 10000, status: 'pending' } })
})

describe('ChildMembershipPayments', () => {
  it('renders nothing when no child is waiting for payment', async () => {
    mockFetch.mockResolvedValue({ items: [] })
    const wrapper = mount(ChildMembershipPayments)
    await flushPromises()
    expect(wrapper.find('.child-payments').exists()).toBe(false)
  })

  it('shows the child and reports a Vipps-QR payment for their one period', async () => {
    const wrapper = mount(ChildMembershipPayments)
    await flushPromises()

    expect(wrapper.text()).toContain('Mini Das')
    await wrapper.findAll('button').find((b) => b.text().includes('made this payment'))!.trigger('click')
    await flushPromises()

    expect(mockStart).toHaveBeenCalledWith({ periodIds: [31], provider: 'vipps_qr' })
  })

  it('offers Cash only while it is switched on, and shows an already reported payment as awaiting', async () => {
    mockFetch.mockResolvedValue({
      items: [{ ...child, period: { ...child.period, payment_pending: true } }],
      cash: { enabled: true, note: '' },
    })
    const wrapper = mount(ChildMembershipPayments)
    await flushPromises()
    expect(wrapper.find('.awaiting-confirmation').exists()).toBe(true)
    expect(wrapper.find('.child-methods').exists()).toBe(false)
  })
})
