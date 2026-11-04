// Tests for MemberTicketsView (7 cases), e.g. MemberTicketsView; shows purchased tickets once orders load; shows a checked-in badge and checkmark for a used ticket.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchMyOrders = vi.fn()

vi.mock('../../../services/ordersApi', () => ({
  fetchMyOrders: (...args: unknown[]) => mockFetchMyOrders(...args),
}))

import MemberTicketsView from '../MemberTicketsView.vue'

beforeEach(() => {
  vi.clearAllMocks()
})

function makeOrder(overrides: Record<string, unknown> = {}) {
  return {
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
    items: [
      {
        id: 1,
        ticket_type_id: 1,
        ticket_type_name: 'Adult',
        quantity: 1,
        unit_price: 15000,
        subtotal: 15000,
        tickets: [{ id: 1, ticket_code: 'abc', status: 'valid', qr_code_data_url: 'data:image/png;base64,x' }],
      },
    ],
    created_at: '2026-09-01T10:00:00Z',
    ...overrides,
  }
}

describe('MemberTicketsView', () => {
  it('shows purchased tickets once orders load', async () => {
    mockFetchMyOrders.mockResolvedValue({ items: [makeOrder()] })

    const wrapper = mount(MemberTicketsView)
    await flushPromises()

    expect(wrapper.text()).toContain('BCA-2026-000001')
    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.find('img[src="data:image/png;base64,x"]').exists()).toBe(true)
  })

  it('shows a checked-in badge and checkmark for a used ticket', async () => {
    mockFetchMyOrders.mockResolvedValue({
      items: [
        makeOrder({
          items: [
            {
              id: 1,
              ticket_type_id: 1,
              ticket_type_name: 'Adult',
              quantity: 1,
              unit_price: 15000,
              subtotal: 15000,
              tickets: [{ id: 1, ticket_code: 'abc', status: 'used', qr_code_data_url: 'data:image/png;base64,x' }],
            },
          ],
        }),
      ],
    })

    const wrapper = mount(MemberTicketsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Checked in')
  })

  it('shows an empty state when there are no orders yet', async () => {
    mockFetchMyOrders.mockResolvedValue({ items: [] })

    const wrapper = mount(MemberTicketsView)
    await flushPromises()

    expect(wrapper.text()).toContain('No tickets yet')
  })

  it('shows an error state when the fetch fails', async () => {
    mockFetchMyOrders.mockRejectedValue(new Error('network error'))

    const wrapper = mount(MemberTicketsView)
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load")
  })

  it('collapses multiple orders by default and expands one on click', async () => {
    mockFetchMyOrders.mockResolvedValue({
      items: [
        makeOrder({ id: 1, order_number: 'BCA-2026-000001', event_title: 'Durga Puja 2026' }),
        makeOrder({
          id: 2,
          order_number: 'BCA-2026-000002',
          event_title: 'Saraswati Puja 2026',
          items: [
            {
              id: 2,
              ticket_type_id: 1,
              ticket_type_name: 'Adult',
              quantity: 1,
              unit_price: 15000,
              subtotal: 15000,
              tickets: [{ id: 2, ticket_code: 'def', status: 'valid', qr_code_data_url: 'data:image/png;base64,y' }],
            },
          ],
        }),
      ],
    })

    const wrapper = mount(MemberTicketsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).toContain('Saraswati Puja 2026')
    expect(wrapper.find('img').exists()).toBe(false)

    const headers = wrapper.findAll('button[aria-expanded]')
    await headers[0].trigger('click')

    expect(wrapper.find('img[src="data:image/png;base64,x"]').exists()).toBe(true)
    expect(wrapper.find('img[src="data:image/png;base64,y"]').exists()).toBe(false)
  })

  it('navigates between tickets in a multi-ticket order via Next/Previous', async () => {
    mockFetchMyOrders.mockResolvedValue({
      items: [
        makeOrder({
          items: [
            {
              id: 1,
              ticket_type_id: 1,
              ticket_type_name: 'Adult',
              quantity: 2,
              unit_price: 15000,
              subtotal: 30000,
              tickets: [
                { id: 1, ticket_code: 'abc', status: 'valid', qr_code_data_url: 'data:image/png;base64,x' },
                { id: 2, ticket_code: 'def', status: 'valid', qr_code_data_url: 'data:image/png;base64,y' },
              ],
            },
          ],
        }),
      ],
    })

    const wrapper = mount(MemberTicketsView)
    await flushPromises()

    expect(wrapper.find('img[src="data:image/png;base64,x"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('1 / 2')

    const nextButton = wrapper.find('button[aria-label="Next ticket"]')
    await nextButton.trigger('click')

    expect(wrapper.find('img[src="data:image/png;base64,y"]').exists()).toBe(true)
    expect(wrapper.find('img[src="data:image/png;base64,x"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('2 / 2')

    const previousButton = wrapper.find('button[aria-label="Previous ticket"]')
    await previousButton.trigger('click')

    expect(wrapper.find('img[src="data:image/png;base64,x"]').exists()).toBe(true)
  })
})
