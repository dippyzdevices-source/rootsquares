// Tests for CheckinOff (3 cases), e.g. accounting page and the Check-in module; on: the check-in rate is shown; off: no check-in rate.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

// A square without the Check-in module (W8-R22): no check-in rate on an event's accounting page.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', async (importOriginal) => ({ ...(await importOriginal<typeof import('../../../services/modules')>()), moduleEnabled: (key?: string) => !off.keys.includes(key ?? '') }))
vi.mock('../../../services/lookupsApi', () => ({ fetchLookup: vi.fn().mockResolvedValue([]) }))
const summary = {
  event: { id: 5, title: 'Durga Puja 2026', slug: 'durga-puja-2026', published: true, start_datetime: '2099-10-10T10:00:00', end_datetime: null },
  collection_total: 350000, expenses_total: 100000, net_total: 250000, tickets_sold: 42, tickets_expected: 40, tickets_checked_in: 10,
  tickets_by_type: [{ name: 'Adult', count: 30 }], tickets_by_sale_mode: [], top_expense_categories: [], coupon_usage: [],
}
vi.mock('../../../services/adminAccountingApi', async () => ({
  ...(await vi.importActual<typeof import('../../../services/adminAccountingApi')>('../../../services/adminAccountingApi')),
  fetchEventAccountingSummary: () => Promise.resolve(summary),
  fetchEventCollections: () => Promise.resolve({ items: [] }),
  fetchEventExpenses: () => Promise.resolve({ items: [], page: 1, per_page: 50, total: 0, total_pages: 0 }),
}))

import AdminAccountingDashboardView from '../AdminAccountingDashboardView.vue'

async function mountView() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/admin/accounting/:eventId', component: AdminAccountingDashboardView }] })
  router.push('/admin/accounting/5')
  await router.isReady()
  const wrapper = mount(AdminAccountingDashboardView, { global: { plugins: [router], stubs: { RouterLink: true } } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  off.keys = []
})

describe('accounting page and the Check-in module', () => {
  it('on: the check-in rate is shown', async () => {
    expect((await mountView()).text()).toContain('Check-in rate')
  })

  it('off: no check-in rate', async () => {
    off.keys = ['checkin']
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).not.toContain('Check-in rate')
    expect(wrapper.text()).not.toContain('checked in')
  })
})
