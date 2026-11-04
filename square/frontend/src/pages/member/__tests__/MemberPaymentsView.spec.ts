// Tests for MemberPaymentsView (8 cases), e.g. MemberPaymentsView; lists past orders as a payment ledger; shows an empty state when there are no payments yet.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchMyOrders = vi.fn()

vi.mock('../../../services/ordersApi', () => ({
  fetchMyOrders: (...args: unknown[]) => mockFetchMyOrders(...args),
}))

const mockFetchMyMembershipPayments = vi.fn()
vi.mock('../../../services/membershipPaymentsApi', () => ({
  fetchMyMembershipPayments: (...args: unknown[]) => mockFetchMyMembershipPayments(...args),
}))

import MemberPaymentsView from '../MemberPaymentsView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchMyMembershipPayments.mockResolvedValue([])
})

describe('MemberPaymentsView', () => {
  it('lists past orders as a payment ledger', async () => {
    mockFetchMyOrders.mockResolvedValue({
      items: [
        {
          id: 1,
          order_number: 'BCA-2026-000001',
          event_id: 1,
          event_title: 'Durga Puja 2026',
          event_start_datetime: '2026-10-10T16:00:00Z',
          customer_name: 'Priya Das',
          customer_email: 'priya@example.com',
          customer_phone: null,
          total_amount: 15000,
          payment_status: 'paid',
          order_status: 'confirmed',
          items: [],
          created_at: '2026-09-01T10:00:00Z',
        },
      ],
    })

    const wrapper = mount(MemberPaymentsView)
    await flushPromises()

    expect(wrapper.text()).toContain('BCA-2026-000001')
    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).toContain('150.00 kr')
    expect(wrapper.text()).toContain('Paid')
  })

  it('shows an empty state when there are no payments yet', async () => {
    mockFetchMyOrders.mockResolvedValue({ items: [] })

    const wrapper = mount(MemberPaymentsView)
    await flushPromises()

    expect(wrapper.text()).toContain('No payments yet')
  })

  it('shows an error state when the fetch fails', async () => {
    mockFetchMyOrders.mockRejectedValue(new Error('network error'))

    const wrapper = mount(MemberPaymentsView)
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load")
  })
})

describe('MemberPaymentsView — membership payments', () => {
  beforeEach(() => {
    mockFetchMyOrders.mockResolvedValue({ items: [] })
  })

  it('shows a membership payments table with the payment reference and amount', async () => {
    mockFetchMyMembershipPayments.mockResolvedValue([
      {
        id: 1,
        payment_reference: 'PAY-2027-000001',
        provider: 'vipps',
        amount: 40000,
        currency: 'NOK',
        status: 'paid',
        paid_at: '2027-01-05T10:00:00+00:00',
        created_at: '2027-01-05T10:00:00+00:00',
        allocations: [
          { amount: 20000, label: 'January 2027' },
          { amount: 20000, label: 'February 2027' },
        ],
      },
    ])

    const wrapper = mount(MemberPaymentsView)
    await flushPromises()

    expect(wrapper.text()).toContain('PAY-2027-000001')
    expect(wrapper.text()).toContain('400.00 kr')
  })

  it('shows an empty state when there are no membership payments', async () => {
    mockFetchMyMembershipPayments.mockResolvedValue([])
    const wrapper = mount(MemberPaymentsView)
    await flushPromises()

    expect(wrapper.text()).toContain('No membership payments yet')
  })

  it('shows an error state when the membership payments fetch fails', async () => {
    mockFetchMyMembershipPayments.mockRejectedValue(new Error('network error'))

    const wrapper = mount(MemberPaymentsView)
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load your membership payments")
  })
})
