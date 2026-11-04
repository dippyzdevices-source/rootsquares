// Tests for AdminOrderDetailView (22 cases), e.g. AdminOrderDetailView; shows mark-as-paid and reject while merely pending (buyer never report; shows mark-as-paid and reject once the buyer has reported payment.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

const mockFetchAdminOrder = vi.fn()
const mockMarkOrderPaid = vi.fn()
const mockRejectOrder = vi.fn()
const mockCancelOrder = vi.fn()
const mockResendConfirmation = vi.fn()

vi.mock('../../../services/adminOrdersApi', () => ({
  fetchAdminOrder: (...args: unknown[]) => mockFetchAdminOrder(...args),
  markOrderPaid: (...args: unknown[]) => mockMarkOrderPaid(...args),
  rejectOrder: (...args: unknown[]) => mockRejectOrder(...args),
  cancelOrder: (...args: unknown[]) => mockCancelOrder(...args),
  resendConfirmation: (...args: unknown[]) => mockResendConfirmation(...args),
}))

import AdminOrderDetailView from '../AdminOrderDetailView.vue'

async function mountAtOrderId(id: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/admin/orders/:id', component: AdminOrderDetailView }],
  })
  router.push(`/admin/orders/${id}`)
  await router.isReady()
  return mount(AdminOrderDetailView, { global: { plugins: [router] } })
}

const baseOrder = {
  id: 1,
  order_number: 'BCA-2026-000001',
  event_id: 1,
  customer_name: 'Priya Das',
  customer_email: 'priya@example.com',
  customer_phone: null,
  total_amount: 15000,
  payment_status: 'pending',
  order_status: 'pending',
  items: [
    {
      id: 1,
      ticket_type_id: 1,
      ticket_type_name: 'Adult',
      quantity: 1,
      unit_price: 15000,
      subtotal: 15000,
      tickets: [],
    },
  ],
  created_at: '2026-09-01T10:00:00Z',
  approved_by_name: null,
  approved_by_email: null,
  approved_at: null,
  rejected_by_name: null,
  rejected_by_email: null,
  rejected_at: null,
  rejection_reason: null,
  cancelled_by_name: null,
  cancelled_by_email: null,
  cancelled_at: null,
  cancellation_reason: null,
}

const pendingVerificationOrder = { ...baseOrder, payment_status: 'pending_verification' }

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminOrder.mockResolvedValue(pendingVerificationOrder)
})

describe('AdminOrderDetailView', () => {
  it('shows mark-as-paid and reject while merely pending (buyer never reported payment)', async () => {
    mockFetchAdminOrder.mockResolvedValue({ ...baseOrder, payment_status: 'pending' })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    expect(wrapper.find('button.mark-paid').exists()).toBe(true)
    expect(wrapper.find('button.reject-order').exists()).toBe(true)
  })

  it('shows mark-as-paid and reject once the buyer has reported payment', async () => {
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    expect(wrapper.find('button.mark-paid').exists()).toBe(true)
    expect(wrapper.find('button.reject-order').exists()).toBe(true)
  })

  it('hides the mark-as-paid/reject buttons once the order is paid', async () => {
    mockFetchAdminOrder.mockResolvedValue({ ...baseOrder, payment_status: 'paid' })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    expect(wrapper.find('button.mark-paid').exists()).toBe(false)
    expect(wrapper.find('button.reject-order').exists()).toBe(false)
  })

  it('marks the order as paid, refreshes the view, and shows an approval feedback banner', async () => {
    mockMarkOrderPaid.mockResolvedValue({
      ...baseOrder,
      payment_status: 'paid',
      approved_by_name: null,
      approved_by_email: 'admin@example.com',
      approved_at: '2026-09-01T12:00:00Z',
      items: [
        {
          ...baseOrder.items[0],
          tickets: [{ id: 1, ticket_code: 'abc', status: 'valid', qr_code_data_url: 'data:image/png;base64,x' }],
        },
      ],
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    await wrapper.find('button.mark-paid').trigger('click')
    await flushPromises()

    expect(mockMarkOrderPaid).toHaveBeenCalledWith(1, 'vipps_qr')
    expect(wrapper.find('button.mark-paid').exists()).toBe(false)
    expect(wrapper.find('img[src="data:image/png;base64,x"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('admin@example.com')
  })

  it('shows a checked-in badge and checkmark for a used ticket', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      payment_status: 'paid',
      items: [
        {
          ...baseOrder.items[0],
          tickets: [{
            id: 1, ticket_code: 'abc', status: 'used', qr_code_data_url: 'data:image/png;base64,x',
            checked_in_at: null, checked_in_by_email: null, checked_in_by_name: null,
          }],
        },
      ],
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    expect(wrapper.text()).toContain('Checked in')
  })

  it('shows the ticket code and who checked it in, when scanned', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      payment_status: 'paid',
      items: [
        {
          ...baseOrder.items[0],
          tickets: [{
            id: 1, ticket_code: 'F7JoGTBl6R_BvHnRJ1KVsw', status: 'used', qr_code_data_url: 'data:image/png;base64,x',
            checked_in_at: '2026-10-10T18:00:00+00:00',
            checked_in_by_email: 'door@example.com',
            checked_in_by_name: 'Door Volunteer',
          }],
        },
      ],
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    expect(wrapper.text()).toContain('F7JoGTBl6R_BvHnRJ1KVsw')
    expect(wrapper.text()).toContain('Door Volunteer')
    expect(wrapper.text()).toContain('door@example.com')
  })

  it('does not show who-checked-in details for an unused ticket', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      payment_status: 'paid',
      items: [
        {
          ...baseOrder.items[0],
          tickets: [{
            id: 1, ticket_code: 'abc', status: 'valid', qr_code_data_url: 'data:image/png;base64,x',
            checked_in_at: null, checked_in_by_email: null, checked_in_by_name: null,
          }],
        },
      ],
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Checked in by')
  })

  it('requires a reason before confirming a rejection', async () => {
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    await wrapper.find('button.reject-order').trigger('click')
    await flushPromises()
    const body = new DOMWrapper(document.body)
    await body.find('button.confirm-reject').trigger('click')

    expect(mockRejectOrder).not.toHaveBeenCalled()
    expect(body.text()).toContain('This field is required.')
    wrapper.unmount()
  })

  it('rejects the order with a reason and shows a failure feedback banner', async () => {
    mockRejectOrder.mockResolvedValue({
      ...baseOrder,
      payment_status: 'rejected',
      order_status: 'cancelled',
      rejected_by_name: null,
      rejected_by_email: 'admin@example.com',
      rejected_at: '2026-09-01T12:00:00Z',
      rejection_reason: "Screenshot doesn't match the order total",
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    await wrapper.find('button.reject-order').trigger('click')
    await flushPromises()
    const body = new DOMWrapper(document.body)
    await body.find('textarea').setValue("Screenshot doesn't match the order total")
    await body.find('button.confirm-reject').trigger('click')
    await flushPromises()

    expect(mockRejectOrder).toHaveBeenCalledWith(1, "Screenshot doesn't match the order total")
    expect(wrapper.find('button.mark-paid').exists()).toBe(false)
    expect(wrapper.text()).toContain('admin@example.com')
    expect(wrapper.text()).toContain("Screenshot doesn't match the order total")
    wrapper.unmount()
  })

  it('shows a Cancel order button only once the order is paid', async () => {
    const pendingWrapper = await mountAtOrderId('1')
    await flushPromises()
    expect(pendingWrapper.find('button.cancel-order').exists()).toBe(false)
    pendingWrapper.unmount()

    mockFetchAdminOrder.mockResolvedValue({ ...baseOrder, payment_status: 'paid' })
    const paidWrapper = await mountAtOrderId('1')
    await flushPromises()
    expect(paidWrapper.find('button.cancel-order').exists()).toBe(true)
    paidWrapper.unmount()
  })

  it('resends the confirmation email from a paid order, and only a paid one has the button', async () => {
    const pendingWrapper = await mountAtOrderId('1')
    await flushPromises()
    expect(pendingWrapper.find('button.resend-confirmation').exists()).toBe(false)
    pendingWrapper.unmount()

    mockFetchAdminOrder.mockResolvedValue({ ...baseOrder, payment_status: 'paid' })
    mockResendConfirmation.mockResolvedValue({ sent_to: 'priya@example.com' })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()
    await wrapper.find('button.resend-confirmation').trigger('click')
    await flushPromises()

    expect(mockResendConfirmation).toHaveBeenCalledWith(1)
    wrapper.unmount()
  })

  it('disables Cancel order with a reason once a ticket is checked in', async () => {
    const items = baseOrder.items.map((item) => ({
      ...item,
      tickets: [{ id: 9, ticket_code: 'used1', status: 'used', qr_code_data_url: 'data:image/png;base64,x', checked_in_at: '2026-10-12T10:00:00Z', checked_in_by_email: null, checked_in_by_name: null }],
    }))
    mockFetchAdminOrder.mockResolvedValue({ ...baseOrder, payment_status: 'paid', items })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()
    expect(wrapper.find('button.cancel-order').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('already been checked in')
    wrapper.unmount()
  })

  it('cancels the order with a reason and shows the cancellation banner', async () => {
    mockFetchAdminOrder.mockResolvedValue({ ...baseOrder, payment_status: 'paid' })
    mockCancelOrder.mockResolvedValue({
      ...baseOrder,
      payment_status: 'cancelled',
      order_status: 'cancelled',
      cancelled_by_name: null,
      cancelled_by_email: 'admin@example.com',
      cancelled_at: '2026-09-28T12:00:00Z',
      cancellation_reason: 'Event postponed',
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    await wrapper.find('button.cancel-order').trigger('click')
    await flushPromises()
    const body = new DOMWrapper(document.body)
    await body.find('textarea').setValue('Event postponed')
    await body.find('button.confirm-cancel').trigger('click')
    await flushPromises()

    expect(mockCancelOrder).toHaveBeenCalledWith(1, 'Event postponed')
    expect(wrapper.find('button.cancel-order').exists()).toBe(false)
    expect(wrapper.text()).toContain('admin@example.com')
    expect(wrapper.text()).toContain('Event postponed')
    wrapper.unmount()
  })

  it('lists the payments of the order with provider and fee, linking to the payments page', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      payment_status: 'paid',
      payments: [
        { id: 7, payment_reference: 'PAY-2026-000007', provider: 'vipps_app', amount: 31500, surcharge_amount: 1500, status: 'paid', paid_at: null, created_at: '2026-10-05T10:00:00+00:00' },
      ],
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    const section = wrapper.find('.order-payments')
    expect(section.exists()).toBe(true)
    expect(section.text()).toContain('PAY-2026-000007')
    expect(section.text()).toContain('Vipps-App')
    expect(section.text()).toContain('15.00 kr')
  })

  it('lets the admin record how the money really arrived (starts on how the order was placed)', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      payments: [{ id: 3, payment_reference: 'PAY-1', provider: 'cash', amount: 15000, surcharge_amount: 0, status: 'pending', paid_at: null, created_at: '2026-09-01T10:00:00Z' }],
    })
    mockMarkOrderPaid.mockResolvedValue({ ...baseOrder, payment_status: 'paid' })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    // Both choices are always visible, with the order's own method already ticked.
    expect((wrapper.find('input[name="paid-with"][value="cash"]').element as HTMLInputElement).checked).toBe(true)
    expect((wrapper.find('input[name="paid-with"][value="vipps_qr"]').element as HTMLInputElement).checked).toBe(false)
    await wrapper.find('input[name="paid-with"][value="vipps_qr"]').setValue(true)
    await wrapper.find('button.mark-paid').trigger('click')
    await flushPromises()

    expect(mockMarkOrderPaid).toHaveBeenCalledWith(1, 'vipps_qr')
  })

  it('shows a green Member pill with the type, links to the member and shows their photo', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      customer_phone: '41234567',
      customer_member: { status: 'member', member_id: 9, membership_type: 'individual', photo_url: 'https://img.test/priya.webp' },
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    const pill = wrapper.find('.customer-pill')
    expect(pill.text()).toBe('Member · Individual')
    expect(pill.classes()).toContain('ds-badge-success')
    expect(wrapper.find('.order-customer a.member-link').exists()).toBe(true)
    expect(wrapper.find('.customer-avatar').attributes('src')).toBe('https://img.test/priya.webp')
    expect(wrapper.find('.order-customer').text()).toContain('41234567')
  })

  it('shows a muted Former member pill, and a Guest pill with initials and no link otherwise', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      customer_member: { status: 'former', member_id: 9, membership_type: 'family', photo_url: null },
    })
    let wrapper = await mountAtOrderId('1')
    await flushPromises()
    expect(wrapper.find('.customer-pill').text()).toBe('Former member · Family')
    expect(wrapper.find('.customer-pill').classes()).toContain('ds-badge-neutral')

    mockFetchAdminOrder.mockResolvedValue({ ...baseOrder, customer_member: { status: 'guest', member_id: null, membership_type: null, photo_url: null } })
    wrapper = await mountAtOrderId('1')
    await flushPromises()
    expect(wrapper.find('.customer-pill').text()).toBe('Guest')
    expect(wrapper.find('.order-customer a.member-link').exists()).toBe(false)
    expect(wrapper.find('.customer-avatar').text()).toBe('PD') // initials of Priya Das
  })

  it('a free order paid by a coupon gets the same green banner and a Payments row naming the coupon', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      payment_status: 'paid',
      order_status: 'confirmed',
      total_amount: 0,
      coupon_code: 'BCAMEMBER26',
      discount_amount: 12500,
      coupon_percent: 100,
      items: [{ ...baseOrder.items[0], unit_price: 12500, subtotal: 12500 }],
      payments: [],
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    const banner = wrapper.find('.paid-banner.ds-alert-success')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('Paid with coupon')
    expect(banner.text()).toContain('Coupon BCAMEMBER26 (100% off)')
    expect(banner.text()).not.toMatch(/no payment/i) // said once, in the Payments row below
    const card = wrapper.find('.order-payments')
    const row = card.find('.coupon-payment-row')
    expect(row.text()).toContain('Coupon BCAMEMBER26 (100% off)')
    // the details sit on their own lines
    const lines = row.findAll('.ds-caption > span').map((l) => l.text())
    expect(lines.slice(0, 3)).toEqual(['Covered the full amount', '125.00 kr off', 'No payment needed'])
    expect(row.text()).toContain('Paid')
    // the Tickets card shows the amount, the coupon with its percentage, then the total
    expect(wrapper.find('.order-subtotal').text()).toContain('125.00 kr')
    expect(wrapper.find('.order-discount').text()).toContain('Coupon BCAMEMBER26 (100% off)')
    expect(wrapper.find('.order-discount').text()).toContain('−125.00 kr')
    expect(wrapper.find('.order-total').text()).toContain('Total')
    expect(wrapper.find('.order-total').text()).toContain('0.00 kr')
    expect(wrapper.find('button.mark-paid').exists()).toBe(false)
  })

  it('a Vipps-App order that Vipps confirmed by itself also gets the green banner', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      payment_status: 'paid',
      order_status: 'confirmed',
      payments: [{ id: 5, payment_reference: 'PAY-5', provider: 'vipps_app', amount: 15750, surcharge_amount: 750, status: 'paid', paid_at: '2026-09-01T10:05:00Z', created_at: '2026-09-01T10:00:00Z' }],
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()
    const banner = wrapper.find('.paid-banner.ds-alert-success')
    expect(banner.text()).toContain('Paid with Vipps-App')
    expect(banner.text()).toContain('Confirmed automatically')
    expect(banner.text()).not.toContain('approve')
  })

  it('keeps tickets in the Tickets card and puts the amounts break-up in the Payments card', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      payment_status: 'paid',
      order_status: 'confirmed',
      payments: [{ id: 5, payment_reference: 'PAY-5', provider: 'vipps_app', amount: 15750, surcharge_amount: 750, status: 'paid', paid_at: '2026-09-01T10:05:00Z', created_at: '2026-09-01T10:00:00Z' }],
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()

    expect(wrapper.find('.order-tickets').text()).not.toContain('kr')
    expect(wrapper.find('.order-tickets .order-total').exists()).toBe(false)
    const payments = wrapper.find('.order-payments')
    expect(payments.find('.order-line').exists()).toBe(true)
    expect(payments.find('.order-total-line').text()).toContain('Total')
    expect(payments.find('.order-fee').text()).toContain('7.50 kr')
    expect(payments.find('.order-charged').text()).toContain('157.50 kr')
  })

  it('an order approved by an admin still shows the original banner (no duplicate)', async () => {
    mockFetchAdminOrder.mockResolvedValue({
      ...baseOrder,
      payment_status: 'paid',
      approved_by_name: 'Admin Person',
      approved_by_email: 'admin@example.com',
      approved_at: '2026-09-01T12:00:00Z',
      coupon_code: null,
      payments: [{ id: 6, payment_reference: 'PAY-6', provider: 'cash', amount: 15000, surcharge_amount: 0, status: 'paid', paid_at: '2026-09-01T12:00:00Z', created_at: '2026-09-01T10:00:00Z' }],
    })
    const wrapper = await mountAtOrderId('1')
    await flushPromises()
    expect(wrapper.findAll('.ds-alert-success').length).toBe(1)
    expect(wrapper.find('.ds-alert-success').text()).toContain('Marked as paid')
  })
})
