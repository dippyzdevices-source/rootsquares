// Tests for AdminTestimonialsOff (3 cases), e.g. admin without the Testimonials module; the dashboard does not ask for pending testimonials; the Home page form has no testimonial words, but keeps the others.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// A square without the Testimonials module (W8-R10): the admin shows and asks for nothing about testimonials.
vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => key !== 'testimonials' }))

const mockFetchAdminTestimonials = vi.fn()
vi.mock('../../../services/adminTestimonialsApi', () => ({ fetchAdminTestimonials: (...args: unknown[]) => mockFetchAdminTestimonials(...args) }))
vi.mock('../../../services/adminEventsApi', () => ({ fetchAdminEvents: () => Promise.resolve({ items: [], total: 1 }) }))
vi.mock('../../../services/adminMembersApi', () => ({ fetchAdminMembers: () => Promise.resolve({ items: [], total: 1 }) }))
vi.mock('../../../services/adminMembershipsApi', () => ({ fetchAdminMemberships: () => Promise.resolve({ items: [], total: 1 }) }))
vi.mock('../../../services/adminOrdersApi', () => ({ fetchAdminOrders: () => Promise.resolve({ items: [], total: 1 }) }))
vi.mock('../../../services/adminReportsApi', () => ({ fetchReportsSummary: () => Promise.reject(new Error('no')) }))
vi.mock('../../../services/adminSettingsApi', async () => ({
  ...(await vi.importActual<typeof import('../../../services/adminSettingsApi')>('../../../services/adminSettingsApi')),
  fetchAdminSettings: () => Promise.resolve({ home_content: {} }),
}))
vi.mock('../../../composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }))

import AdminDashboardView from '../AdminDashboardView.vue'
import AdminHomeContentView from '../AdminHomeContentView.vue'

const stubs = { SettingsSectionNav: true, SettingsBackButton: true, RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => vi.clearAllMocks())

describe('admin without the Testimonials module', () => {
  it('the dashboard does not ask for pending testimonials', async () => {
    setActivePinia(createPinia())
    const wrapper = mount(AdminDashboardView, { global: { stubs } })
    await flushPromises()
    expect(mockFetchAdminTestimonials).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('testimonial')
  })

  it('the Home page form has no testimonial words, but keeps the others', async () => {
    const wrapper = mount(AdminHomeContentView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('[aria-label="Small line above the testimonial"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Button to send a testimonial"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Small line above the association text"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="Small line above the sponsors"]').exists()).toBe(true) // the Sponsors module is on here
  })
})
