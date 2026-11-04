// Tests for MemberLayout (7 cases), e.g. MemberLayout; renders the shared site header; renders the shared site footer.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import MemberLayout from '../MemberLayout.vue'

vi.mock('../../services/supabaseClient', () => ({
  supabase: { auth: { signOut: vi.fn().mockResolvedValue({ error: null }) } },
}))

const mockFetchMyMember = vi.fn()
const mockFetchMyOrders = vi.fn()
const mockFetchMyMembershipPayments = vi.fn()
const mockFetchMyTaskAssignments = vi.fn()

vi.mock('../../services/memberApi', async () => {
  const actual = await vi.importActual<typeof import('../../services/memberApi')>('../../services/memberApi')
  return {
    ...actual,
    fetchMyMember: (...args: unknown[]) => mockFetchMyMember(...args),
    fetchMyTaskAssignments: (...args: unknown[]) => mockFetchMyTaskAssignments(...args),
  }
})
vi.mock('../../services/ordersApi', () => ({ fetchMyOrders: (...args: unknown[]) => mockFetchMyOrders(...args) }))
vi.mock('../../services/membershipPaymentsApi', () => ({
  fetchMyMembershipPayments: (...args: unknown[]) => mockFetchMyMembershipPayments(...args),
}))

const stubs = { RouterLink: { template: '<a><slot /></a>' }, RouterView: true }

function mountLayout() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/', component: { template: '<div/>' } }],
  })
  return mount(MemberLayout, { global: { stubs, plugins: [router] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null, family_members: [{ id: 1, name: 'Anita', relationship_type: 'spouse', age: 34, sort_order: 0 }] })
  mockFetchMyOrders.mockResolvedValue({ items: [{ id: 1 }, { id: 2 }, { id: 3 }] })
  mockFetchMyMembershipPayments.mockResolvedValue([
    { id: 1, payment_reference: 'PAY-1', provider: 'vipps', amount: 20000, currency: 'NOK', status: 'paid', paid_at: '2026-01-01', created_at: '2026-01-01', allocations: [] },
  ])
  mockFetchMyTaskAssignments.mockResolvedValue([{ id: 1 }])
})

describe('MemberLayout', () => {
  it('renders the shared site header', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('header').exists()).toBe(true)
  })

  it('renders the shared site footer', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('footer').exists()).toBe(true)
  })

  it('renders one sidebar nav link per portal section', () => {
    const wrapper = mountLayout()

    expect(wrapper.findAll('.ds-appshell__links a')).toHaveLength(6)
  })

  it('links back to the public site from the header brand', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('a[to="/"]').exists()).toBe(true)
  })

  it('shows a live item count badge on sections that have one', async () => {
    const wrapper = mountLayout()
    await flushPromises()

    const familyLink = wrapper.find('a[to="/member/family"]')
    expect(familyLink.find('.ds-appshell__link-count').text()).toBe('1')
    const ticketsLink = wrapper.find('a[to="/member/tickets"]')
    expect(ticketsLink.find('.ds-appshell__link-count').text()).toBe('3')
    const volunteeringLink = wrapper.find('a[to="/member/volunteering"]')
    expect(volunteeringLink.find('.ds-appshell__link-count').text()).toBe('1')
    const paymentsLink = wrapper.find('a[to="/member/payments"]')
    expect(paymentsLink.find('.ds-appshell__link-count').text()).toBe('4')
  })

  it('does not show a count badge on sections without one', async () => {
    const wrapper = mountLayout()
    await flushPromises()

    const overviewLink = wrapper.find('a[to="/member"]')
    expect(overviewLink.find('.ds-appshell__link-count').exists()).toBe(false)
  })
})
