// Tests for AdminOrdersListView (12 cases), e.g. AdminOrdersListView; lists orders with their order number and payment status; opens the order when a row is tapped, but not when its own link is.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chooseOption, selectedLabel } from '../../../test-utils/baseSelect'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminOrders = vi.fn()
const mockExportOrders = vi.fn()

vi.mock('../../../services/adminEventsApi', () => ({
  fetchAdminEvents: vi.fn().mockResolvedValue({
    items: [
      { id: 7, title: 'Durga Puja 2026' },
      { id: 9, title: 'Saraswati Puja 2027' },
    ],
  }),
}))

vi.mock('../../../services/adminOrdersApi', () => ({
  fetchAdminOrders: (...args: unknown[]) => mockFetchAdminOrders(...args),
  exportOrders: (...args: unknown[]) => mockExportOrders(...args),
}))

vi.mock('../../../utils/download', () => ({
  downloadBlob: vi.fn(),
}))

// Bare object rather than a real router — this view only reads `route.query` (never
// navigates), matching this codebase's convention for components using the bare
// `<router-link>` tag rather than an imported `RouterLink`.
const mockRoute: { query: Record<string, string> } = { query: {} }
const mockPush = vi.fn()
vi.mock('vue-router', () => ({ useRoute: () => mockRoute, useRouter: () => ({ push: mockPush }) }))

import AdminOrdersListView from '../AdminOrdersListView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mockRoute.query = {}
  mockFetchAdminOrders.mockResolvedValue({
    items: [
      {
        id: 1,
        order_number: 'BCA-2026-000001',
        event_id: 1,
        customer_name: 'Priya Das',
        customer_email: 'priya@example.com',
        customer_phone: null,
        total_amount: 15000,
        payment_status: 'pending',
        order_status: 'pending',
        items: [],
        created_at: '2026-09-01T10:00:00Z',
      },
    ],
    page: 1,
    per_page: 20,
    total: 1,
    total_pages: 1,
  })
})

describe('AdminOrdersListView', () => {
  it('lists orders with their order number and payment status', async () => {
    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(mockFetchAdminOrders).toHaveBeenCalled()
    expect(wrapper.text()).toContain('BCA-2026-000001')
    expect(wrapper.text()).toContain('Pending')
  })

  it('opens the order when a row is tapped, but not when its own link is', async () => {
    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    await wrapper.find('tbody tr a').trigger('click')
    expect(mockPush).not.toHaveBeenCalled()

    await wrapper.find('tbody tr td').trigger('click')
    expect(mockPush).toHaveBeenCalledWith(expect.stringMatching(/^\/admin\/orders\/\d+$/))
  })

  it('searches orders on Enter, sending the text as q and starting from page 1', async () => {
    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    mockFetchAdminOrders.mockClear()

    const input = wrapper.find('input[type="search"]')
    expect(input.exists()).toBe(true)
    await input.setValue('priya')
    await input.trigger('keyup', { key: 'Enter' })
    await flushPromises()

    expect(mockFetchAdminOrders).toHaveBeenCalledWith(expect.objectContaining({ q: 'priya', page: 1 }))
  })

  it('puts the search before the status filter in the toolbar', async () => {
    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    const toolbar = wrapper.find('.ds-toolbar')
    expect(toolbar.element.children[0].classList.contains('ds-toolbar-search')).toBe(true)
    expect(toolbar.element.children[1].classList.contains('base-select')).toBe(true)
  })

  it('filters by event, sending the event id and starting from page 1', async () => {
    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    mockFetchAdminOrders.mockClear()

    await chooseOption(wrapper, '9', 0)
    await flushPromises()

    expect(mockFetchAdminOrders).toHaveBeenCalledWith(expect.objectContaining({ eventId: ['9'], page: 1 }))
    expect(selectedLabel(wrapper, 0)).toBe('Saraswati Puja 2027')
  })

  it('refetches when the payment status filter changes', async () => {
    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    mockFetchAdminOrders.mockClear()

    await chooseOption(wrapper, 'paid', 1)
    await flushPromises()

    expect(mockFetchAdminOrders).toHaveBeenCalledWith(
      expect.objectContaining({ paymentStatus: ['paid'] }),
    )
  })

  it('lets several payment statuses be ticked at once', async () => {
    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    mockFetchAdminOrders.mockClear()

    await chooseOption(wrapper, 'paid', 1)
    await chooseOption(wrapper, 'cancelled', 1)
    await flushPromises()

    expect(mockFetchAdminOrders).toHaveBeenLastCalledWith(
      expect.objectContaining({ paymentStatus: ['paid', 'cancelled'] }),
    )
    expect(selectedLabel(wrapper, 1)).toBe('2 selected')
  })

  it('pre-selects the payment status filter from a ?status= query param', async () => {
    mockRoute.query = { status: 'pending' }

    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(mockFetchAdminOrders).toHaveBeenCalledWith(
      expect.objectContaining({ paymentStatus: ['pending'] }),
    )
    expect(selectedLabel(wrapper, 1)).toBe('Pending')
  })

  it('ticks both statuses when the dashboard banner link asks for several', async () => {
    mockRoute.query = { status: 'pending,pending_verification' }

    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(mockFetchAdminOrders).toHaveBeenCalledWith(
      expect.objectContaining({ paymentStatus: ['pending', 'pending_verification'] }),
    )
    expect(selectedLabel(wrapper, 1)).toBe('2 selected')
  })

  it('exports orders to Excel', async () => {
    const blob = new Blob(['xlsx-data'])
    mockExportOrders.mockResolvedValue(blob)

    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    await wrapper.find('button.export-orders').trigger('click')
    await flushPromises()

    expect(mockExportOrders).toHaveBeenCalled()
  })

  it('exports with the search that is on screen', async () => {
    mockExportOrders.mockResolvedValue(new Blob(['xlsx-data']))

    const wrapper = mount(AdminOrdersListView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    const input = wrapper.find('input[type="search"]')
    await input.setValue('priya')
    await input.trigger('keyup', { key: 'Enter' })
    await flushPromises()
    await wrapper.find('button.export-orders').trigger('click')
    await flushPromises()

    expect(mockExportOrders).toHaveBeenCalledWith(expect.objectContaining({ q: 'priya' }))
  })
})
