// Tests for OrderLookupView (6 cases), e.g. OrderLookupView; looks up an order by number and email and shows the result; shows a checked-in badge for a used ticket.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockLookupOrder = vi.fn()

vi.mock('../../../services/ordersApi', () => ({
  lookupOrder: (...args: unknown[]) => mockLookupOrder(...args),
}))

let mockRouteQuery: Record<string, string> = {}
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: mockRouteQuery }),
}))

import OrderLookupView from '../OrderLookupView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mockRouteQuery = {}
})

describe('OrderLookupView', () => {
  it('looks up an order by number and email and shows the result', async () => {
    mockLookupOrder.mockResolvedValue({
      id: 1,
      order_number: 'BCA-2026-000001',
      payment_status: 'paid',
      total_amount: 15000,
      items: [
        {
          id: 1,
          ticket_type_name: 'Adult',
          quantity: 1,
          unit_price: 15000,
          subtotal: 15000,
          tickets: [{ id: 1, ticket_code: 'abc', status: 'valid', qr_code_data_url: 'data:image/png;base64,x' }],
        },
      ],
    })

    const wrapper = mount(OrderLookupView)

    await wrapper.find('input[placeholder="Order number"]').setValue('BCA-2026-000001')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('button.lookup-order').trigger('click')
    await flushPromises()

    expect(mockLookupOrder).toHaveBeenCalledWith('BCA-2026-000001', 'priya@example.com')
    expect(wrapper.text()).toContain('Paid')
    expect(wrapper.find('img[src="data:image/png;base64,x"]').exists()).toBe(true)
  })

  it('shows a checked-in badge for a used ticket', async () => {
    mockLookupOrder.mockResolvedValue({
      id: 1,
      order_number: 'BCA-2026-000001',
      payment_status: 'paid',
      total_amount: 15000,
      items: [
        {
          id: 1,
          ticket_type_name: 'Adult',
          quantity: 1,
          unit_price: 15000,
          subtotal: 15000,
          tickets: [{ id: 1, ticket_code: 'abc', status: 'used', qr_code_data_url: 'data:image/png;base64,x' }],
        },
      ],
    })

    const wrapper = mount(OrderLookupView)

    await wrapper.find('input[placeholder="Order number"]').setValue('BCA-2026-000001')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('button.lookup-order').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Checked in')
  })

  it('shows an error when the order is not found', async () => {
    mockLookupOrder.mockRejectedValue(new Error('Order not found'))

    const wrapper = mount(OrderLookupView)

    await wrapper.find('input[placeholder="Order number"]').setValue('BCA-2026-999999')
    await wrapper.find('input[placeholder="Email address"]').setValue('wrong@example.com')
    await wrapper.find('button.lookup-order').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('not found')
  })

  it('pre-fills and auto-submits from order_number/email query params', async () => {
    mockRouteQuery = { order_number: 'BCA-2026-000001', email: 'priya@example.com' }
    mockLookupOrder.mockResolvedValue({
      id: 1,
      order_number: 'BCA-2026-000001',
      payment_status: 'pending',
      total_amount: 15000,
      items: [],
    })

    const wrapper = mount(OrderLookupView)
    await flushPromises()

    expect(mockLookupOrder).toHaveBeenCalledWith('BCA-2026-000001', 'priya@example.com')
    expect((wrapper.find('input[placeholder="Order number"]').element as HTMLInputElement).value).toBe(
      'BCA-2026-000001',
    )
    expect((wrapper.find('input[placeholder="Email address"]').element as HTMLInputElement).value).toBe(
      'priya@example.com',
    )
  })

  it('does not auto-submit when query params are absent', async () => {
    const wrapper = mount(OrderLookupView)
    await flushPromises()

    expect(mockLookupOrder).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('Order BCA')
  })
})
