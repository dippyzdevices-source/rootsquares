// Tests for AdminEventsOff (2 cases), e.g. admin dashboard without the Events module; does not ask for events and has no events card.
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// A square without the Events module (W8-R28): the admin dashboard has no events card and does not ask for events.
vi.mock('../../../services/modules', async (importOriginal) => ({ ...(await importOriginal<typeof import('../../../services/modules')>()), moduleEnabled: (key?: string) => key !== 'events' }))
const mockEvents = vi.fn()
vi.mock('../../../services/adminEventsApi', () => ({ fetchAdminEvents: (...a: unknown[]) => mockEvents(...a) }))
vi.mock('../../../services/adminMembersApi', () => ({ fetchAdminMembers: () => Promise.resolve({ items: [], total: 1 }) }))
vi.mock('../../../services/adminMembershipsApi', () => ({ fetchAdminMemberships: () => Promise.resolve({ items: [], total: 0 }) }))
vi.mock('../../../services/adminOrdersApi', () => ({ fetchAdminOrders: () => Promise.resolve({ items: [], total: 0 }) }))
vi.mock('../../../services/adminTestimonialsApi', () => ({ fetchAdminTestimonials: () => Promise.resolve({ items: [], total: 0 }) }))
vi.mock('../../../services/adminReportsApi', () => ({ fetchReportsSummary: () => Promise.reject(new Error('no')) }))

import AdminDashboardView from '../AdminDashboardView.vue'

describe('admin dashboard without the Events module', () => {
  it('does not ask for events and has no events card', async () => {
    setActivePinia(createPinia())
    const wrapper = mount(AdminDashboardView, { global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } } })
    await flushPromises()
    expect(mockEvents).not.toHaveBeenCalled()
    expect(wrapper.find('a[href="/admin/events"]').exists()).toBe(false)
  })
})
