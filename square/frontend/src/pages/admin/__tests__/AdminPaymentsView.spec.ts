// Tests for AdminPaymentsView (17 cases), e.g. AdminPaymentsView; exports payments to Excel; tapping a row opens its order or member, but not when the tap is on a.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chooseOption } from '../../../test-utils/baseSelect'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mockPush }) }))

vi.mock('../../../composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

const mockFetchAdminPayments = vi.fn()
const mockRefundPayment = vi.fn()
const mockExportPayments = vi.fn()
const mockCheckVipps = vi.fn()
const mockStartTest = vi.fn()
const mockVippsStatus = vi.fn()
vi.mock('../../../services/adminPaymentsApi', () => ({
  fetchAdminPayments: (...args: unknown[]) => mockFetchAdminPayments(...args),
  refundPayment: (...args: unknown[]) => mockRefundPayment(...args),
  exportPayments: (...args: unknown[]) => mockExportPayments(...args),
  checkVippsPayment: (...args: unknown[]) => mockCheckVipps(...args),
  startVippsTestPayment: (...args: unknown[]) => mockStartTest(...args),
  fetchVippsStatus: (...args: unknown[]) => mockVippsStatus(...args),
}))

vi.mock('../../../utils/download', () => ({
  downloadBlob: vi.fn(),
}))

import AdminPaymentsView from '../AdminPaymentsView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mockVippsStatus.mockResolvedValue({ configured: true, public: false })
  mockFetchAdminPayments.mockResolvedValue({
    items: [
      {
        id: 1, payment_reference: 'PAY-2027-000001', payment_type: 'membership',
        payer_name: 'Priya Das', order_id: null, provider: 'vipps_qr', amount: 20000,
        currency: 'NOK', status: 'paid', paid_at: '2027-01-05T10:00:00+00:00',
        created_at: '2027-01-05T10:00:00+00:00',
        allocations: [{ amount: 20000, label: 'January 2027' }],
      },
    ],
    page: 1, per_page: 20, total: 1, total_pages: 1,
  })
})

describe('AdminPaymentsView', () => {
  it('exports payments to Excel', async () => {
    const blob = new Blob(['xlsx-data'])
    mockExportPayments.mockResolvedValue(blob)

    const wrapper = mount(AdminPaymentsView)
    await flushPromises()

    await wrapper.find('button.export-payments').trigger('click')
    await flushPromises()

    expect(mockExportPayments).toHaveBeenCalled()
  })

  it('tapping a row opens its order or member, but not when the tap is on a button or the test payment', async () => {
    mockFetchAdminPayments.mockResolvedValue({
      items: [
        { id: 1, payment_reference: 'PAY-1', payment_type: 'membership', payer_name: 'Priya Das', member_id: 42, order_id: null, provider: 'vipps', amount: 20000, currency: 'NOK', status: 'paid', paid_at: null, created_at: '2027-01-05T10:00:00+00:00', allocations: [] },
        { id: 2, payment_reference: 'PAY-2', payment_type: 'event_ticket', payer_name: 'Ritu Sen', member_id: null, order_id: 9, order_number: 'BCA-2027-000009', provider: 'manual', amount: 30000, currency: 'NOK', status: 'paid', paid_at: null, created_at: '2027-01-05T10:00:00+00:00', allocations: [] },
        { id: 3, payment_reference: 'PAY-3', payment_type: 'vipps_test', payer_name: 'Vipps test payment (admin)', member_id: null, order_id: null, provider: 'vipps_app', amount: 105, currency: 'NOK', status: 'paid', paid_at: null, created_at: '2027-01-05T10:00:00+00:00', allocations: [] },
      ],
      page: 1, per_page: 20, total: 3, total_pages: 1,
    })
    const wrapper = mount(AdminPaymentsView, { global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } } })
    await flushPromises()
    const rows = wrapper.findAll('tbody tr')

    await rows[0].trigger('click')
    expect(mockPush).toHaveBeenLastCalledWith('/admin/members/42')
    await rows[1].trigger('click')
    expect(mockPush).toHaveBeenLastCalledWith('/admin/orders/9')

    mockPush.mockClear()
    await rows[2].trigger('click') // test payment: nothing to open
    await rows[1].find('button.refund-payment').trigger('click') // a button keeps its own action
    expect(mockPush).not.toHaveBeenCalled()
    expect(rows[2].classes()).not.toContain('ds-row-clickable')
    expect(rows[1].classes()).toContain('ds-row-clickable')
    wrapper.unmount() // the button tap opened the refund modal (teleported to body)
  })
})


describe('AdminPaymentsView — reconciliation', () => {
  it('lists payments with who paid, amount, and status', async () => {
    const wrapper = mount(AdminPaymentsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('PAY-2027-000001')
    expect(wrapper.text()).toContain('200.00 kr')
    expect(wrapper.text()).toContain('Paid')
  })

  it('shows the customer name and reference for a ticket payment', async () => {
    mockFetchAdminPayments.mockResolvedValue({
      items: [
        {
          id: 2, payment_reference: 'PAY-2027-000002', payment_type: 'event_ticket',
          payer_name: 'Ritu Sen', order_id: 5, provider: 'manual', amount: 15000,
          currency: 'NOK', status: 'paid', paid_at: '2027-01-05T10:00:00+00:00',
          created_at: '2027-01-05T10:00:00+00:00', allocations: [],
        },
      ],
      page: 1, per_page: 20, total: 1, total_pages: 1,
    })

    const wrapper = mount(AdminPaymentsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Ritu Sen')
    expect(wrapper.text()).toContain('PAY-2027-000002')
  })

  it('manual payment: needs two confirmations (warning, then "I have returned the money") before refunding', async () => {
    mockRefundPayment.mockResolvedValue({ id: 1, status: 'refunded' })
    const wrapper = mount(AdminPaymentsView)
    await flushPromises()
    const body = new DOMWrapper(document.body)

    await wrapper.find('button.refund-payment').trigger('click')
    await flushPromises()
    expect(body.text()).toContain('not paid through Vipps-App')
    expect(body.find('button.refund-confirm').exists()).toBe(false)
    expect(mockRefundPayment).not.toHaveBeenCalled()

    await body.find('button.refund-continue').trigger('click')
    expect(body.text()).toContain('Second check')
    expect((body.find('button.refund-confirm').element as HTMLButtonElement).disabled).toBe(true)

    await body.find('input.money-returned').setValue(true)
    await body.find('button.refund-confirm').trigger('click')
    await flushPromises()

    expect(mockRefundPayment).toHaveBeenCalledWith(1, expect.any(String))
    wrapper.unmount()
  })

  it('Vipps App payment: one confirmation, then refunds', async () => {
    mockFetchAdminPayments.mockResolvedValue({
      items: [
        {
          id: 5, payment_reference: 'PAY-2027-000005', payment_type: 'event_ticket',
          payer_name: 'Priya Das', order_id: 3, provider: 'vipps_app', amount: 31500, surcharge_amount: 1500,
          refund_mode: 'vipps', refund_blocked_reason: null,
          currency: 'NOK', status: 'paid', paid_at: '2027-01-05T10:00:00+00:00',
          created_at: '2027-01-05T10:00:00+00:00', allocations: [],
        },
      ],
      page: 1, per_page: 20, total: 1, total_pages: 1,
    })
    mockRefundPayment.mockResolvedValue({ id: 5, status: 'refunded' })
    const wrapper = mount(AdminPaymentsView)
    await flushPromises()
    const body = new DOMWrapper(document.body)

    expect(wrapper.find('.payment-provider').text()).toBe('Vipps-App')
    await wrapper.find('button.refund-payment').trigger('click')
    await flushPromises()
    expect(body.text()).toContain('through Vipps right now')
    await body.find('button.refund-confirm').trigger('click')
    await flushPromises()

    expect(mockRefundPayment).toHaveBeenCalledWith(5, expect.any(String))
    wrapper.unmount()
  })

  it('disables Refund and explains why when the backend says it is blocked', async () => {
    mockFetchAdminPayments.mockResolvedValue({
      items: [
        {
          id: 6, payment_reference: 'PAY-2027-000006', payment_type: 'event_ticket',
          payer_name: 'Priya Das', order_id: 4, provider: 'manual', amount: 30000,
          refund_mode: 'manual', refund_blocked_reason: 'Refunds are not allowed after the event day.',
          currency: 'NOK', status: 'paid', paid_at: '2027-01-05T10:00:00+00:00',
          created_at: '2027-01-05T10:00:00+00:00', allocations: [],
        },
      ],
      page: 1, per_page: 20, total: 1, total_pages: 1,
    })
    const wrapper = mount(AdminPaymentsView)
    await flushPromises()
    const button = wrapper.find('button.refund-payment')
    expect((button.element as HTMLButtonElement).disabled).toBe(true)
    expect(button.attributes('title')).toContain('after the event day')
  })

  it('links a membership payment to the member page and a ticket payment to its order', async () => {
    mockFetchAdminPayments.mockResolvedValue({
      items: [
        { id: 1, payment_reference: 'PAY-1', payment_type: 'membership', payer_name: 'Priya Das', member_id: 42, order_id: null, provider: 'vipps', amount: 20000, currency: 'NOK', status: 'paid', paid_at: null, created_at: '2027-01-05T10:00:00+00:00', allocations: [] },
        { id: 2, payment_reference: 'PAY-2', payment_type: 'event_ticket', payer_name: 'Ritu Sen', member_id: null, order_id: 9, order_number: 'BCA-2027-000009', provider: 'manual', amount: 30000, currency: 'NOK', status: 'paid', paid_at: null, created_at: '2027-01-05T10:00:00+00:00', allocations: [] },
      ],
      page: 1, per_page: 20, total: 2, total_pages: 1,
    })
    const wrapper = mount(AdminPaymentsView, { global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } } })
    await flushPromises()

    expect(wrapper.find('a.member-link').attributes('href')).toBe('/admin/members/42')
    expect(wrapper.find('a.order-link').attributes('href')).toBe('/admin/orders/9')
  })
})


describe('AdminPaymentsView — filters, search, and pagination', () => {
  it('re-fetches with the selected type/status/provider filters', async () => {
    const wrapper = mount(AdminPaymentsView)
    await flushPromises()

    await chooseOption(wrapper, 'membership', 0)
    await flushPromises()

    expect(mockFetchAdminPayments).toHaveBeenLastCalledWith(
      expect.objectContaining({ payment_type: ['membership'], page: 1 }),
    )

    await chooseOption(wrapper, 'paid', 1)
    await flushPromises()
    expect(mockFetchAdminPayments).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: ['paid'] }),
    )

    await chooseOption(wrapper, 'vipps_qr', 2)
    await flushPromises()
    expect(mockFetchAdminPayments).toHaveBeenLastCalledWith(
      expect.objectContaining({ provider: ['vipps_qr'] }),
    )
  })

  it('searches on enter', async () => {
    const wrapper = mount(AdminPaymentsView)
    await flushPromises()

    await wrapper.find('input').setValue('Priya')
    await wrapper.find('input').trigger('keyup.enter')
    await flushPromises()

    expect(mockFetchAdminPayments).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: 'Priya' }),
    )
  })

  it('shows pagination controls and pages forward', async () => {
    mockFetchAdminPayments.mockResolvedValue({
      items: [
        {
          id: 1, payment_reference: 'PAY-2027-000001', payment_type: 'membership',
          payer_name: 'Priya Das', order_id: null, provider: 'vipps_qr', amount: 20000,
          currency: 'NOK', status: 'paid', paid_at: null, created_at: '2027-01-05T10:00:00+00:00',
          allocations: [],
        },
      ],
      page: 1, per_page: 20, total: 40, total_pages: 2,
    })

    const wrapper = mount(AdminPaymentsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Page 1 of 2')
    await wrapper.findAll('button').find((b) => b.text() === 'Next')!.trigger('click')
    await flushPromises()

    expect(mockFetchAdminPayments).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }))
  })

  it('offers "Check with Vipps" for a Vipps App payment still at Vipps and calls the backend', async () => {
    mockFetchAdminPayments.mockResolvedValue({
      items: [
        {
          id: 9, payment_reference: 'PAY-2027-000009', payment_type: 'event_ticket',
          payer_name: 'Priya Das', order_id: 3, provider: 'vipps_app', amount: 31500,
          currency: 'NOK', status: 'initiated', paid_at: null,
          created_at: '2027-01-05T10:00:00+00:00', allocations: [],
        },
      ],
      page: 1, per_page: 20, total: 1, total_pages: 1,
    })
    mockCheckVipps.mockResolvedValue({ id: 9, status: 'paid' })

    const wrapper = mount(AdminPaymentsView)
    await flushPromises()
    await wrapper.find('button.check-vipps').trigger('click')
    await flushPromises()

    expect(mockCheckVipps).toHaveBeenCalledWith(9)
  })

  it('starts the 1 kr Vipps test payment and sends the admin to Vipps', async () => {
    mockStartTest.mockResolvedValue({ redirect_url: 'https://vipps.test/pay' })
    const hrefSet = vi.fn()
    Object.defineProperty(window, 'location', { configurable: true, value: { set href(v: string) { hrefSet(v) } } })

    const wrapper = mount(AdminPaymentsView)
    await flushPromises()
    await wrapper.find('button.vipps-test-payment').trigger('click')
    await flushPromises()

    expect(mockStartTest).toHaveBeenCalled()
    expect(hrefSet).toHaveBeenCalledWith('https://vipps.test/pay')
  })

  it('hides the Vipps test button once Vipps App is public, or when not configured', async () => {
    mockVippsStatus.mockResolvedValue({ configured: true, public: true })
    let wrapper = mount(AdminPaymentsView)
    await flushPromises()
    expect(wrapper.find('button.vipps-test-payment').exists()).toBe(false)

    mockVippsStatus.mockResolvedValue({ configured: false, public: false })
    wrapper = mount(AdminPaymentsView)
    await flushPromises()
    expect(wrapper.find('button.vipps-test-payment').exists()).toBe(false)
  })
})
