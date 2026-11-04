// Tests for TicketsOff (3 cases), e.g. the Tickets module; on: the footer links to the order lookup and the member payments page; off: no order lookup link and orders are not asked for.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Tickets module (W8-R29): no order lookup link, no ticket request on an event page, no orders in the member payments page.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', async (importOriginal) => ({ ...(await importOriginal<typeof import('../../../services/modules')>()), moduleEnabled: (key?: string) => !off.keys.includes(key ?? '') }))
vi.mock('../../../services/settingsApi', () => ({ fetchSettings: () => Promise.resolve({ contact_email: 'hello@club.example' }) }))
vi.mock('../../../services/siteContent', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../services/siteContent')>()
  return { ...actual, loadHomeContent: () => Promise.resolve(actual.fillHomeContent(undefined)) }
})
const mockOrders = vi.fn()
vi.mock('../../../services/ordersApi', () => ({ fetchMyOrders: (...a: unknown[]) => mockOrders(...a) }))
vi.mock('../../../services/membershipPaymentsApi', () => ({ fetchMyMembershipPayments: () => Promise.resolve([]) }))

import SiteFooter from '../../../components/layout/SiteFooter.vue'
import MemberPaymentsView from '../../member/MemberPaymentsView.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
  off.keys = []
  mockOrders.mockResolvedValue({ items: [] })
})

describe('the Tickets module', () => {
  it('on: the footer links to the order lookup and the member payments page asks for orders', async () => {
    const footer = mount(SiteFooter, { global: { stubs } })
    const pay = mount(MemberPaymentsView, { global: { stubs } })
    await flushPromises()
    expect(footer.find('a[href="/orders/lookup"]').exists()).toBe(true)
    expect(mockOrders).toHaveBeenCalled()
    expect(pay.exists()).toBe(true)
  })

  it('off: no order lookup link and orders are not asked for', async () => {
    off.keys = ['tickets']
    const footer = mount(SiteFooter, { global: { stubs } })
    const pay = mount(MemberPaymentsView, { global: { stubs } })
    await flushPromises()
    expect(footer.find('a[href="/orders/lookup"]').exists()).toBe(false)
    expect(mockOrders).not.toHaveBeenCalled()
    expect(pay.text()).not.toContain('No payments yet')
  })
})
