// Tests for MemberLayoutModules (4 cases), e.g. MemberLayout and the modules; all on: six sections; Memberships off (an Event pass): no Family, Volunteering stays.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import MemberLayout from '../MemberLayout.vue'

// The member area follows the modules (W8-R19, W8-R20): a section of a module that is off has no sidebar item and no request.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../services/modules', async (importOriginal) => ({ ...(await importOriginal<typeof import('../../services/modules')>()), moduleEnabled: (key?: string) => !off.keys.includes(key ?? '') }))
vi.mock('../../services/supabaseClient', () => ({ supabase: { auth: { signOut: vi.fn().mockResolvedValue({ error: null }) } } }))
const mockTasks = vi.fn()
vi.mock('../../services/memberApi', async () => ({
  ...(await vi.importActual<typeof import('../../services/memberApi')>('../../services/memberApi')),
  fetchMyMember: () => Promise.resolve({ id: 1, name: 'P', family_members: [] }),
  fetchMyTaskAssignments: (...a: unknown[]) => mockTasks(...a),
}))
vi.mock('../../services/ordersApi', () => ({ fetchMyOrders: () => Promise.resolve({ items: [] }) }))
vi.mock('../../services/membershipPaymentsApi', () => ({ fetchMyMembershipPayments: () => Promise.resolve([]) }))

function mountLayout() {
  const router = createRouter({ history: createWebHistory(), routes: [{ path: '/', component: { template: '<div/>' } }] })
  return mount(MemberLayout, { global: { stubs: { RouterLink: { props: ['to'], template: '<a :to="to"><slot /></a>' }, RouterView: true }, plugins: [router] } })
}
const sidebar = (w: ReturnType<typeof mountLayout>) => w.findAll('.ds-appshell__links a').map((a) => a.attributes('to'))

beforeEach(() => {
  setActivePinia(createPinia())
  off.keys = []
  mockTasks.mockReset()
  mockTasks.mockResolvedValue([])
})

describe('MemberLayout and the modules', () => {
  it('all on: six sections', () => {
    expect(sidebar(mountLayout())).toEqual(['/member', '/member/family', '/member/tickets', '/member/volunteering', '/member/payments', '/member/settings'])
  })

  it('Memberships off (an Event pass): no Family, Volunteering stays', () => {
    off.keys = ['memberships']
    expect(sidebar(mountLayout())).toEqual(['/member', '/member/tickets', '/member/volunteering', '/member/payments', '/member/settings'])
  })

  it('Members and Volunteering off (Volunteering needs Members): no Family, no Volunteering, and volunteering is not asked for', async () => {
    off.keys = ['members', 'memberships', 'volunteering']
    const wrapper = mountLayout()
    await flushPromises()
    expect(sidebar(wrapper)).toEqual(['/member', '/member/tickets', '/member/payments', '/member/settings'])
    expect(mockTasks).not.toHaveBeenCalled()
  })
})
