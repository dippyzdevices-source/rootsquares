// Tests for MemberDashboardView (33 cases), e.g. MemberDashboardView; shows the profile name once loaded; prompts to add contact details when there is no profile yet.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

const mockFetchMyMember = vi.fn()
const mockFetchMyMemberships = vi.fn()
const mockFetchMembershipTypes = vi.fn()
const mockRequestMembershipRenewal = vi.fn()
const mockFetchMyTaskAssignments = vi.fn()
const mockCancelRequest = vi.fn()

vi.mock('../../../services/memberApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/memberApi')>(
    '../../../services/memberApi',
  )
  return {
    ...actual,
    fetchMyMember: (...args: unknown[]) => mockFetchMyMember(...args),
    fetchMyMemberships: (...args: unknown[]) => mockFetchMyMemberships(...args),
    fetchMembershipTypes: (...args: unknown[]) => mockFetchMembershipTypes(...args),
    requestMembershipRenewal: (...args: unknown[]) => mockRequestMembershipRenewal(...args),
    fetchMyTaskAssignments: (...args: unknown[]) => mockFetchMyTaskAssignments(...args),
    cancelMyMembershipRequest: (...args: unknown[]) => mockCancelRequest(...args),
  }
})

const mockFetchMyPeriods = vi.fn()
const mockStartPeriodPayment = vi.fn()

vi.mock('../../../services/membershipPaymentsApi', () => ({
  fetchMyPeriods: (...args: unknown[]) => mockFetchMyPeriods(...args),
  startPeriodPayment: (...args: unknown[]) => mockStartPeriodPayment(...args),
}))

const mockFetchMyOrders = vi.fn()

vi.mock('../../../services/ordersApi', () => ({
  fetchMyOrders: (...args: unknown[]) => mockFetchMyOrders(...args),
}))

import MemberDashboardView from '../MemberDashboardView.vue'
import { MemberNotFoundError } from '../../../services/memberApi'

function mountView() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/', component: { template: '<div/>' } }],
  })
  return mount(MemberDashboardView, { global: { plugins: [router] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  mockFetchMyMemberships.mockResolvedValue([])
  mockFetchMembershipTypes.mockResolvedValue([
    { name: 'individual', price: 500, billing_frequency: 'yearly', contact_for_price: false },
    { name: 'family', price: 800, billing_frequency: 'yearly', contact_for_price: false },
  ])
  mockFetchMyPeriods.mockResolvedValue({ membership: null, items: [] })
  mockFetchMyOrders.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })
  mockFetchMyTaskAssignments.mockResolvedValue([])
})

describe('MemberDashboardView', () => {
  it('shows the profile name once loaded', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
  })

  it('prompts to add contact details when there is no profile yet', async () => {
    mockFetchMyMember.mockRejectedValue(new MemberNotFoundError())

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain("You don't have a profile yet.")
  })

  it('shows an empty state when there are no upcoming ticketed events', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('No upcoming tickets')
  })

  it('shows up to 2 upcoming events with their ticket counts', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    const futureOrder = (id: number, title: string, daysAhead: number) => ({
      id,
      order_number: `BCA-2026-00000${id}`,
      event_title: title,
      event_start_datetime: new Date(Date.now() + daysAhead * 86400000).toISOString(),
      customer_email: 'priya@example.com',
      total_amount: 1000,
      payment_status: 'paid',
      items: [{ id: 1, ticket_type_id: 1, ticket_type_name: 'General', quantity: 2, unit_price: 500, subtotal: 1000, tickets: [{ id: 1, ticket_code: 'a', status: 'valid', qr_code_data_url: '' }, { id: 2, ticket_code: 'b', status: 'valid', qr_code_data_url: '' }] }],
    })
    mockFetchMyOrders.mockResolvedValue({
      items: [futureOrder(1, 'Durga Puja', 10), futureOrder(2, 'Saraswati Puja', 20), futureOrder(3, 'Rabindra Jayanti', 30)],
      page: 1,
      per_page: 20,
      total: 3,
      total_pages: 1,
    })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Durga Puja')
    expect(wrapper.text()).toContain('Saraswati Puja')
    expect(wrapper.text()).not.toContain('Rabindra Jayanti')
    expect(wrapper.text()).toContain('2 seat(s)')
    expect(wrapper.text()).toContain('Confirmed')
  })

  it('excludes upcoming orders that are not confirmed (paid)', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    const order = (id: number, title: string, paymentStatus: string) => ({
      id,
      order_number: `BCA-2026-00000${id}`,
      event_title: title,
      event_start_datetime: new Date(Date.now() + 86400000).toISOString(),
      customer_email: 'priya@example.com',
      total_amount: 500,
      payment_status: paymentStatus,
      items: [{ id: 1, ticket_type_id: 1, ticket_type_name: 'General', quantity: 1, unit_price: 500, subtotal: 500, tickets: [{ id: 1, ticket_code: 'a', status: 'valid', qr_code_data_url: '' }] }],
    })
    mockFetchMyOrders.mockResolvedValue({
      items: [order(1, 'Pending Event', 'pending_verification'), order(2, 'Cancelled Event', 'cancelled')],
      page: 1,
      per_page: 20,
      total: 2,
      total_pages: 1,
    })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).not.toContain('Pending Event')
    expect(wrapper.text()).not.toContain('Cancelled Event')
    expect(wrapper.text()).toContain('No upcoming tickets')
  })

  it('opens a QR modal for an upcoming ticket when "Show" is clicked', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    mockFetchMyOrders.mockResolvedValue({
      items: [
        {
          id: 1,
          order_number: 'BCA-2026-000001',
          event_title: 'Durga Puja',
          event_start_datetime: new Date(Date.now() + 86400000).toISOString(),
          customer_email: 'priya@example.com',
          total_amount: 500,
          payment_status: 'paid',
          items: [{ id: 1, ticket_type_id: 1, ticket_type_name: 'General', quantity: 1, unit_price: 500, subtotal: 500, tickets: [{ id: 1, ticket_code: 'abc123', status: 'valid', qr_code_data_url: 'data:image/png;base64,' }] }],
        },
      ],
      page: 1,
      per_page: 20,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mountView()
    await flushPromises()

    const body = new DOMWrapper(document.body)
    expect(body.find('[role="dialog"]').exists()).toBe(false)
    await wrapper.find('button.ds-btn-secondary').trigger('click')

    expect(body.find('[role="dialog"]').exists()).toBe(true)
    expect(body.text()).toContain('abc123')
    wrapper.unmount()
  })

  it('shows an empty state when there is no upcoming volunteering task', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('No upcoming volunteering')
  })

  it('shows the next upcoming volunteering task', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    mockFetchMyTaskAssignments.mockResolvedValue([
      {
        id: 1, category: 'food', event_id: 1, event_title: 'Durga Puja 2026',
        event_slug: 'durga-puja-2026', event_start_datetime: new Date(Date.now() + 86400000).toISOString(),
        event_end_datetime: null,
      },
      {
        id: 2, category: 'decoration', event_id: 2, event_title: 'Saraswati Puja 2020',
        event_slug: 'saraswati-puja-2020', event_start_datetime: '2020-01-01T10:00:00Z',
        event_end_datetime: null,
      },
    ])

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Next volunteering')
    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).toContain('Food')
    expect(wrapper.text()).not.toContain('Saraswati Puja 2020')
  })

  it('shows the membership status when one exists', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    mockFetchMyMemberships.mockResolvedValue([
      { id: 1, membership_type: 'individual', status: 'active', start_date: '2026-01-01', end_date: null },
    ])

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('active')
    expect(wrapper.text()).toContain('Individual')
  })

  it('shows an empty state when there is no membership', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('No membership yet')
  })

  it('shows a request-renewal control when there is no pending request', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('button.request-renewal').exists()).toBe(true)
  })

  it('always says "Request membership" when nothing is active — first request or after an expired/cancelled one', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })

    mockFetchMyMemberships.mockResolvedValue([])
    const first = mountView()
    await flushPromises()
    expect(first.find('button.request-renewal').text()).toBe('Request membership')
    expect(first.text()).toContain('Join the community')

    for (const status of ['expired', 'cancelled', 'suspended']) {
      mockFetchMyMemberships.mockResolvedValue([
        { id: 1, membership_type: 'individual', status, start_date: '2025-01-01', end_date: '2025-12-31' },
      ])
      const returning = mountView()
      await flushPromises()
      expect(returning.find('button.request-renewal').text()).toBe('Request membership')
      expect(returning.text()).not.toContain('renewal')
    }
  })

  it('calls a pending request a membership request', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    mockFetchMyMemberships.mockResolvedValue([
      { id: 1, membership_type: 'individual', status: 'pending', start_date: '2026-10-01', end_date: null },
    ])

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Membership request pending')
    expect(wrapper.text()).not.toContain('Renewal request pending')
  })

  it('hides the request-renewal control and shows a notice when already active', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    mockFetchMyMemberships.mockResolvedValue([
      { id: 1, membership_type: 'individual', status: 'active', start_date: '2026-01-01', end_date: null },
    ])

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('button.request-renewal').exists()).toBe(false)
    expect(wrapper.text()).toContain('You already have an active Individual membership.')
  })

  it('labels each renewal option with its price and billing frequency', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Individual')
    expect(wrapper.text()).toContain('500 kr / year')
  })

  it('requests a renewal and shows the resulting pending membership', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    mockRequestMembershipRenewal.mockResolvedValue({
      id: 2,
      membership_type: 'family',
      status: 'pending',
      start_date: '2026-09-10',
      end_date: null,
    })

    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('button.request-renewal').trigger('click')
    await flushPromises()

    expect(mockRequestMembershipRenewal).toHaveBeenCalledWith('individual')
    expect(wrapper.text()).toContain('pending')
    expect(wrapper.find('button.request-renewal').exists()).toBe(false)
  })
})

describe('MemberDashboardView — pay first, then active', () => {
  const profile = { id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] }
  const pendingMembership = { id: 2, membership_type: 'individual', status: 'pending', start_date: '2026-10-06', end_date: null }
  const pendingPeriods = (paymentPending = false) => ({
    membership: { id: 2, membership_type: 'individual', status: 'pending' },
    items: [
      { id: 301, period_start: '2026-10-01', period_end: '2026-10-31', label: 'October 2026', amount: 50000, currency: 'NOK', status: 'unpaid', payment_pending: paymentPending, paid_at: null },
    ],
    vipps_app: { enabled: false, surcharge_percent: 5 },
    vipps_qr: { enabled: true, number: '24680' }, // the square's own Vipps number (W6-R38)
    type_changes: [],
  })

  beforeEach(() => {
    mockFetchMyMember.mockResolvedValue(profile)
  })

  it('after requesting, tells the member to pay and opens the payment options for the current period', async () => {
    mockFetchMyPeriods.mockResolvedValueOnce({ membership: null, items: [] }).mockResolvedValue(pendingPeriods())
    mockRequestMembershipRenewal.mockResolvedValue(pendingMembership)

    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('button.request-renewal').trigger('click')
    await flushPromises()

    expect(wrapper.find('.pay-to-activate').text()).toContain('One more step')
    expect(wrapper.find('.pay-to-activate').text()).toContain('October 2026')
    // The one payable period is preselected, so the Vipps panel is already showing.
    expect(wrapper.text()).toContain("I've made this payment")
    expect(wrapper.text()).not.toContain('awaiting admin approval')
  })

  it('says the payment is awaiting confirmation once the member has reported it', async () => {
    mockFetchMyMemberships.mockResolvedValue([pendingMembership])
    mockFetchMyPeriods.mockResolvedValue(pendingPeriods(true))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.pay-to-activate').text()).toContain('Payment reported')
    expect(wrapper.find('.change-plan').exists()).toBe(false)
  })

  it('keeps the "awaiting admin approval" message for a request that has nothing to pay', async () => {
    mockFetchMyMemberships.mockResolvedValue([pendingMembership])
    mockFetchMyPeriods.mockResolvedValue({ membership: null, items: [] })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.pay-to-activate').exists()).toBe(false)
    expect(wrapper.text()).toContain('awaiting admin approval')
  })

  it('lets the member cancel an unpaid request after confirming, back to the request form', async () => {
    mockFetchMyMemberships.mockResolvedValue([pendingMembership])
    mockFetchMyPeriods.mockResolvedValueOnce(pendingPeriods()).mockResolvedValue({ membership: null, items: [] })
    mockCancelRequest.mockResolvedValue(undefined)

    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('.cancel-request').trigger('click')
    expect(mockCancelRequest).not.toHaveBeenCalled()
    await new DOMWrapper(document.body).find('.confirm-cancel-request').trigger('click')
    await flushPromises()

    expect(mockCancelRequest).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.pay-to-activate').exists()).toBe(false)
    expect(wrapper.find('button.request-renewal').text()).toBe('Request membership')
    wrapper.unmount()
  })

  it('offers no cancel once a payment has been reported', async () => {
    mockFetchMyMemberships.mockResolvedValue([pendingMembership])
    mockFetchMyPeriods.mockResolvedValue(pendingPeriods(true))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.cancel-request').exists()).toBe(false)
    wrapper.unmount()
  })

  it('lets the member switch type before paying, which replaces the unpaid request', async () => {
    mockFetchMyMemberships.mockResolvedValue([pendingMembership])
    mockFetchMyPeriods.mockResolvedValue(pendingPeriods())
    mockRequestMembershipRenewal.mockResolvedValue({ ...pendingMembership, id: 3, membership_type: 'individual' })

    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('button.request-renewal').exists()).toBe(false)

    await wrapper.find('.change-plan').trigger('click')
    expect(wrapper.find('button.request-renewal').text()).toBe('Switch membership')
    await wrapper.find('button.request-renewal').trigger('click')
    await flushPromises()

    expect(mockRequestMembershipRenewal).toHaveBeenCalledTimes(1)
    expect(wrapper.find('button.request-renewal').exists()).toBe(false) // back to the payment view
  })
})

describe('MemberDashboardView — period checklist', () => {
  beforeEach(() => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [] })
    mockFetchMyPeriods.mockResolvedValue({
      vipps_qr: { enabled: true, number: '24680' }, // the square's own Vipps number (W6-R38)
      membership: { id: 1, membership_type: 'individual', status: 'active' },
      items: [
        {
          id: 101,
          period_start: '2027-01-01',
          period_end: '2027-01-31',
          label: 'January 2027',
          amount: 20000,
          currency: 'NOK',
          status: 'unpaid',
          paid_at: null,
        },
      ],
    })
  })

  it('shows unpaid periods as selectable tiles with a price', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('January 2027')
    expect(wrapper.text()).toContain('200.00 kr')
  })

  it('shows an explicit error instead of silently looking like no unpaid periods when the fetch fails', async () => {
    mockFetchMyPeriods.mockRejectedValue(new Error('Failed to fetch periods: 500'))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load your unpaid periods")
    expect(wrapper.text()).not.toContain('Choose periods to pay')
  })

  it('shows a muted note when the membership type was changed', async () => {
    mockFetchMyPeriods.mockResolvedValue({
      membership: { id: 1, membership_type: 'Family', status: 'active' },
      items: [],
      type_changes: [{ from_type: 'Individual', to_type: 'Family', changed_at: '2026-03-01T10:00:00Z' }],
    })
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.type-change-note').text()).toContain('changed from Individual to Family')
  })

  it('shows a running total when a period is selected', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('button.ms-tile').trigger('click')

    expect(wrapper.text()).toContain('1 period selected')
    expect(wrapper.text()).toContain('200.00 kr')
  })

  it('shows the Vipps panel on the right once a period is selected, then reports the payment with the selected period id', async () => {
    mockStartPeriodPayment.mockResolvedValue({
      payment: { id: 1, payment_reference: 'PAY-2027-000001', amount: 20000, status: 'pending' },
    })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('button.ms-tile').trigger('click')

    expect(wrapper.find('.vipps-panel').exists()).toBe(true)
    expect(mockStartPeriodPayment).not.toHaveBeenCalled()

    await wrapper.findAll('button').find((b) => b.text() === "I've made this payment")!.trigger('click')
    await flushPromises()

    expect(mockStartPeriodPayment).toHaveBeenCalledWith({ periodIds: [101], provider: 'vipps_qr' })
  })

  it('offers Pay in the Vipps app with a 5% fee line when enabled, and redirects to Vipps', async () => {
    const periods = await mockFetchMyPeriods()
    mockFetchMyPeriods.mockResolvedValue({ ...periods, vipps_app: { enabled: true, surcharge_percent: 5 } })
    mockStartPeriodPayment.mockResolvedValue({
      payment: { id: 7, payment_reference: 'PAY-1', amount: 21000, surcharge_amount: 1000, status: 'initiated' },
      redirect_url: 'https://vipps.test/pay',
    })
    const hrefSet = vi.fn()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { search: '', pathname: '/member', set href(v: string) { hrefSet(v) } },
    })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('button.ms-tile').trigger('click')
    await wrapper.find('input[name="ms-pay"][value="app"]').setValue(true)

    expect(wrapper.find('.vipps-app-panel').text()).toContain('Convenience fee')
    expect(wrapper.find('.vipps-app-panel').text()).toContain('210.00 kr')

    await wrapper.findAll('button').find((b) => b.text().includes('with Vipps'))!.trigger('click')
    await flushPromises()

    expect(mockStartPeriodPayment).toHaveBeenCalledWith({ periodIds: [101], provider: 'vipps_app' })
    expect(hrefSet).toHaveBeenCalledWith('https://vipps.test/pay')
  })

  it('offers Cash with the admin-written wording when enabled, and reports it for an admin to confirm', async () => {
    const periods = await mockFetchMyPeriods()
    mockFetchMyPeriods.mockResolvedValue({ ...periods, cash: { enabled: true, note: 'Pay a committee member.' } })
    mockStartPeriodPayment.mockResolvedValue({ payment: { id: 8, payment_reference: 'PAY-2', amount: 20000, status: 'pending' } })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('button.ms-tile').trigger('click')
    expect(wrapper.find('input[name="ms-pay"][value="app"]').exists()).toBe(false) // Vipps-App is off
    await wrapper.find('input[name="ms-pay"][value="cash"]').setValue(true)

    expect(wrapper.find('.cash-panel .cash-note').text()).toContain('Pay a committee member.')
    expect(wrapper.find('.vipps-panel').exists()).toBe(false)

    await wrapper.findAll('button').find((b) => b.text().includes('in cash'))!.trigger('click')
    await flushPromises()

    expect(mockStartPeriodPayment).toHaveBeenCalledWith({ periodIds: [101], provider: 'cash' })
  })

  it('offers Bank transfer with the account details (empty fields left out) and reports it for an admin to confirm', async () => {
    const periods = await mockFetchMyPeriods()
    mockFetchMyPeriods.mockResolvedValue({
      ...periods,
      bank: { enabled: true, details: { holder: 'Asha Club', bank_name: '', account_number: '', iban: 'NO9386011117947', bic: '', note: 'Allow two days' } },
    })
    mockStartPeriodPayment.mockResolvedValue({ payment: { id: 9, payment_reference: 'PAY-3', amount: 20000, status: 'pending' } })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('button.ms-tile').trigger('click')
    await wrapper.find('input[name="ms-pay"][value="bank"]').setValue(true)

    const text = wrapper.find('.bank-panel').text()
    expect(text).toContain('Asha Club')
    expect(text).toContain('NO9386011117947')
    expect(text).toContain('Allow two days')
    expect(text).not.toContain('BIC')

    await wrapper.find('.bank-reported').trigger('click')
    await flushPromises()

    expect(mockStartPeriodPayment).toHaveBeenCalledWith({ periodIds: [101], provider: 'bank_transfer' })
  })
})
