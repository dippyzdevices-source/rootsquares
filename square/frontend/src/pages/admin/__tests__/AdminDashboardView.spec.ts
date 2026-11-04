// Tests for AdminDashboardView (9 cases), e.g. AdminDashboardView; greets the admin and offers the quick actions; lists what needs attention, with counts and the pending/verification s.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const mockFetchAdminEvents = vi.fn()
const mockFetchAdminMembers = vi.fn()
const mockFetchAdminMemberships = vi.fn()
const mockFetchAdminOrders = vi.fn()
const mockFetchAdminTestimonials = vi.fn()
const mockFetchReportsSummary = vi.fn()
const mockFetchEventAccountingSummary = vi.fn()

vi.mock('../../../services/adminEventsApi', () => ({
  fetchAdminEvents: (...args: unknown[]) => mockFetchAdminEvents(...args),
}))
vi.mock('../../../services/adminMembersApi', () => ({
  fetchAdminMembers: (...args: unknown[]) => mockFetchAdminMembers(...args),
}))
vi.mock('../../../services/adminMembershipsApi', () => ({
  fetchAdminMemberships: (...args: unknown[]) => mockFetchAdminMemberships(...args),
}))
vi.mock('../../../services/adminOrdersApi', () => ({
  fetchAdminOrders: (...args: unknown[]) => mockFetchAdminOrders(...args),
}))
vi.mock('../../../services/adminTestimonialsApi', () => ({
  fetchAdminTestimonials: (...args: unknown[]) => mockFetchAdminTestimonials(...args),
}))
vi.mock('../../../services/adminReportsApi', () => ({
  fetchReportsSummary: (...args: unknown[]) => mockFetchReportsSummary(...args),
}))
vi.mock('../../../services/adminAccountingApi', () => ({
  fetchEventAccountingSummary: (...args: unknown[]) => mockFetchEventAccountingSummary(...args),
}))

import AdminDashboardView from '../AdminDashboardView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }
const mountView = async () => {
  const wrapper = mount(AdminDashboardView, { global: { stubs } })
  await flushPromises()
  return wrapper
}

const latestEvent = {
  id: 2, title: 'Durga Puja 2026', slug: 'durga-puja-2026', published: true,
  start_datetime: '2020-10-16T10:00:00', end_datetime: '2020-10-18T22:00:00',
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.clearAllMocks()
  mockFetchAdminEvents.mockResolvedValue({ items: [latestEvent], page: 1, per_page: 1, total: 3, total_pages: 3 })
  mockFetchAdminMembers.mockImplementation((_q: string, _r: string, _n: number, status?: string[]) =>
    Promise.resolve({ items: [], page: 1, per_page: 20, total: status?.length ? 1 : 41, total_pages: 3 }),
  )
  mockFetchAdminMemberships.mockResolvedValue({ items: [], page: 1, per_page: 1, total: 2, total_pages: 2 })
  mockFetchAdminOrders.mockImplementation((filter: { perPage?: number; paymentStatus?: string }) =>
    Promise.resolve(
      filter.paymentStatus
        ? { items: [], page: 1, per_page: 1, total: 5, total_pages: 5 }
        : {
            items: [
              { id: 1, order_number: 'BCA-2026-000232', customer_name: 'Mousumi Sukul', total_amount: 23500, coupon_code: null, payment_status: 'paid', created_at: '2026-10-18T10:00:00' },
              { id: 2, order_number: 'BCA-2026-000230', customer_name: 'Himangshu Kar', total_amount: 0, coupon_code: 'OSMSUN26', payment_status: 'pending', created_at: '2026-10-18T09:00:00' },
            ],
            page: 1, per_page: 4, total: 219, total_pages: 55,
          },
    ),
  )
  mockFetchAdminTestimonials.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 1 })
  mockFetchReportsSummary.mockResolvedValue({
    revenue_total: 4848800,
    tickets_total: 731,
    memberships_by_status: { active: 35, pending: 2, expired: 1 },
    memberships_by_type: { adult: 30, child: 5 },
    memberships_active_by_type: { adult: 30, child: 5 },
    orders_by_status: { paid: 189, rejected: 22, cancelled: 3, pending: 3, pending_verification: 2 },
  })
  mockFetchEventAccountingSummary.mockResolvedValue({
    net_total: 7074400, tickets_sold: 635, tickets_expected: 635, tickets_checked_in: 0,
    coupon_usage: [{ coupon_code: 'A', tickets_count: 420, gross_total: 5931000, discount_total: 5700200 }],
  })
})

describe('AdminDashboardView', () => {
  it('greets the admin and offers the quick actions', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('h1').text()).toMatch(/^Good (morning|afternoon|evening)/)
    expect(wrapper.text()).toContain('+ New event')
    expect(wrapper.text()).toContain('Send newsletter')
    expect(wrapper.find('.customise-button').exists()).toBe(true)
  })

  it('lists what needs attention, with counts and the pending/verification split', async () => {
    const wrapper = await mountView()
    expect(mockFetchAdminMemberships).toHaveBeenCalledWith(expect.objectContaining({ status: 'pending' }))
    expect(mockFetchAdminOrders).toHaveBeenCalledWith(expect.objectContaining({ paymentStatus: 'pending,pending_verification' }))
    expect(mockFetchAdminTestimonials).toHaveBeenCalledWith('pending', 1)

    const todo = wrapper.find('.dash-todo').text()
    expect(todo).toContain('Orders awaiting payment confirmation')
    expect(todo).toContain('3 pending · 2 pending verification')
    expect(todo).toContain('Membership requests awaiting review')
    expect(todo).toContain('Membership expired')
    expect(todo).toContain('Check-ins for Durga Puja 2026')
    expect(todo).toContain('0 of 635 tickets scanned: event has ended')
  })

  it('says so when nothing needs attention', async () => {
    mockFetchAdminMemberships.mockResolvedValue({ items: [], total: 0 })
    mockFetchAdminMembers.mockResolvedValue({ items: [], total: 0 })
    mockFetchAdminOrders.mockImplementation((filter: { paymentStatus?: string }) =>
      Promise.resolve({ items: [], page: 1, per_page: 1, total: filter.paymentStatus ? 0 : 0, total_pages: 0 }),
    )
    mockFetchReportsSummary.mockResolvedValue({
      revenue_total: 0, tickets_total: 0, memberships_by_status: {}, memberships_by_type: {},
      memberships_active_by_type: {}, orders_by_status: {},
    })
    mockFetchEventAccountingSummary.mockResolvedValue({ net_total: 0, tickets_sold: 0, tickets_expected: 0, tickets_checked_in: 0, coupon_usage: [] })
    const wrapper = await mountView()
    expect(wrapper.find('.dash-todo').text()).toContain('Nothing needs your attention right now.')
  })

  it('shows the four key numbers with their notes', async () => {
    const wrapper = await mountView()
    const kpis = wrapper.find('.dash-kpis').text().replace(/ /g, ' ')
    expect(kpis).toContain('48 488 kr')
    expect(kpis).toContain('Across 3 events')
    expect(kpis).toContain('731')
    expect(kpis).toContain('of 219 · 86% success')
    expect(kpis).toContain('30 adult · 5 child')
  })

  it('shows the latest event with its net result, tickets, check-in and coupon discount', async () => {
    const wrapper = await mountView()
    const card = wrapper.find('.dash-event').text().replace(/ /g, ' ')
    expect(card).toContain('Durga Puja 2026')
    expect(card).toContain('Expired')
    expect(card).toContain('70 744 kr')
    expect(card).toContain('635')
    expect(card).toContain('420')
    expect(card).toContain('0 of 635')
    expect(card).toContain('57 002 kr of 59 310 kr')
  })

  it('breaks orders down by status and lists the latest orders and the membership split', async () => {
    const wrapper = await mountView()
    const orders = wrapper.find('.dash-orders').text()
    expect(orders).toContain('Paid')
    expect(orders).toContain('189')
    expect(orders).toContain('Pending verification')

    const recent = wrapper.find('.dash-recent').text().replace(/ /g, ' ')
    expect(recent).toContain('Mousumi Sukul')
    expect(recent).toContain('BCA-2026-000232')
    expect(recent).toContain('235.00 kr')
    expect(recent).toContain('Coupon OSMSUN26')

    const members = wrapper.find('.dash-members').text()
    expect(members).toContain('35')
    expect(members).toContain('Adult')
    expect(members).toContain('Expired')
  })

  it('lets the admin hide a widget and remembers the choice', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.dash-orders').exists()).toBe(true)

    await wrapper.find('.customise-button').trigger('click')
    const box = new DOMWrapper(document.body).find('input[data-widget="orders"]')
    await box.setValue(false)
    expect(wrapper.find('.dash-orders').exists()).toBe(false)
    expect(JSON.parse(localStorage.getItem('admin-dashboard-widgets-v1') ?? '{}').orders).toBe(false)

    wrapper.unmount()
    const again = await mountView()
    expect(again.find('.dash-orders').exists()).toBe(false)
    again.unmount()
  })

  it('still renders when the secondary calls fail', async () => {
    mockFetchReportsSummary.mockRejectedValue(new Error('boom'))
    mockFetchEventAccountingSummary.mockRejectedValue(new Error('boom'))
    mockFetchAdminTestimonials.mockRejectedValue(new Error('boom'))
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Latest event')
    expect(wrapper.text()).toContain('Durga Puja 2026')
  })
})
