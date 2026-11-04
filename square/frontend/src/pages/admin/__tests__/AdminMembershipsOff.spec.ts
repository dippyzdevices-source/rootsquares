// Tests for AdminMembershipsOff (2 cases), e.g. admin dashboard without the Memberships module; does not ask for members or memberships and shows no member cards.
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// A square without the Memberships module (W8-R19): the admin dashboard asks for and shows nothing about members.
vi.mock('../../../services/modules', async (importOriginal) => ({ ...(await importOriginal<typeof import('../../../services/modules')>()), moduleEnabled: (key?: string) => key !== 'memberships' && key !== 'members' }))
const mockMembers = vi.fn()
const mockMemberships = vi.fn()
vi.mock('../../../services/adminEventsApi', () => ({ fetchAdminEvents: () => Promise.resolve({ items: [], total: 2 }) }))
vi.mock('../../../services/adminMembersApi', () => ({ fetchAdminMembers: (...a: unknown[]) => mockMembers(...a) }))
vi.mock('../../../services/adminMembershipsApi', () => ({ fetchAdminMemberships: (...a: unknown[]) => mockMemberships(...a) }))
vi.mock('../../../services/adminOrdersApi', () => ({ fetchAdminOrders: () => Promise.resolve({ items: [], total: 0 }) }))
vi.mock('../../../services/adminTestimonialsApi', () => ({ fetchAdminTestimonials: () => Promise.resolve({ items: [], total: 0 }) }))
vi.mock('../../../services/adminReportsApi', () => ({
  fetchReportsSummary: () => Promise.resolve({ revenue_total: 0, tickets_total: 0, memberships_by_status: {}, memberships_by_type: {}, orders_by_status: { paid: 1 } }),
}))

import AdminDashboardView from '../AdminDashboardView.vue'

describe('admin dashboard without the Memberships module', () => {
  it('does not ask for members or memberships and shows no member cards', async () => {
    setActivePinia(createPinia())
    const wrapper = mount(AdminDashboardView, { global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } } })
    await flushPromises()
    expect(mockMembers).not.toHaveBeenCalled()
    expect(mockMemberships).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('Memberships by')
    expect(wrapper.find('a[href="/admin/members"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Latest event')  // the events part of the dashboard stays
  })
})
