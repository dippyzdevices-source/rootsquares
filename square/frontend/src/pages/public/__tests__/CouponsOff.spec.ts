// Tests for CouponsOff (3 cases), e.g. ticket page and the Coupons module; on: there is a coupon box; off: no coupon box.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

// A square without the Coupons module (W8-R21): the ticket page has no coupon box.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', async (importOriginal) => ({ ...(await importOriginal<typeof import('../../../services/modules')>()), moduleEnabled: (key?: string) => !off.keys.includes(key ?? '') }))
vi.mock('../../../services/supabaseClient', () => ({ supabase: { auth: { signOut: vi.fn() } } }))
vi.mock('../../../services/eventsApi', async () => ({
  ...(await vi.importActual<typeof import('../../../services/eventsApi')>('../../../services/eventsApi')),
  fetchEvent: () => Promise.resolve({ id: 1, title: 'Fest', slug: 'fest', start_datetime: '2030-07-01T18:00:00', end_datetime: null, venue: 'Hall', published: true, coupon_max_adult: null, coupon_max_child: null, max_tickets_per_email: null }),
}))
vi.mock('../../../services/ticketsApi', async () => ({
  ...(await vi.importActual<typeof import('../../../services/ticketsApi')>('../../../services/ticketsApi')),
  fetchTicketTypes: () => Promise.resolve({ items: [{ id: 1, name: 'Adult', price: 10000, currency: 'NOK', available: 10, sold_out: false, coupon_eligible: true, age_category: 'adult', description: '' }] }),
}))
vi.mock('../../../services/couponsApi', () => ({ validateCoupon: vi.fn() }))

import TicketPurchaseView from '../TicketPurchaseView.vue'

async function mountPage() {
  const router = createRouter({ history: createWebHistory(), routes: [{ path: '/events/:slug/tickets', component: TicketPurchaseView }, { path: '/:p(.*)*', component: { template: '<div/>' } }] })
  await router.push('/events/fest/tickets')
  await router.isReady()
  return mount(TicketPurchaseView, { global: { plugins: [router, createPinia()] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  off.keys = []
})

describe('ticket page and the Coupons module', () => {
  it('on: there is a coupon box', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    expect(wrapper.find('input[placeholder="SAVE20"]').exists()).toBe(true)
  })

  it('off: no coupon box', async () => {
    off.keys = ['coupons']
    const wrapper = await mountPage()
    await flushPromises()
    expect(wrapper.find('input[placeholder="SAVE20"]').exists()).toBe(false)
  })
})
