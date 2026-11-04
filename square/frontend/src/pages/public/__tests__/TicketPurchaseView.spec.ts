// Tests for TicketPurchaseView (35 cases), e.g. TicketPurchaseView; shows ticket types with formatted prices; shows multi-day tickets in a tab per day, all-days passes last, one da.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchEvent = vi.fn()
const mockFetchTicketTypes = vi.fn()
const mockCheckout = vi.fn()
const mockValidateCoupon = vi.fn()
const mockVippsConfig = vi.fn()

vi.mock('../../../services/eventsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/eventsApi')>(
    '../../../services/eventsApi',
  )
  return { ...actual, fetchEvent: (...args: unknown[]) => mockFetchEvent(...args) }
})

vi.mock('../../../services/ticketsApi', () => ({
  fetchTicketTypes: (...args: unknown[]) => mockFetchTicketTypes(...args),
}))

vi.mock('../../../services/ordersApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/ordersApi')>(
    '../../../services/ordersApi',
  )
  return { ...actual, checkout: (...args: unknown[]) => mockCheckout(...args) }
})

vi.mock('../../../services/couponsApi', () => ({
  validateCoupon: (...args: unknown[]) => mockValidateCoupon(...args),
}))

vi.mock('../../../services/vippsAppApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/vippsAppApi')>('../../../services/vippsAppApi')
  return { ...actual, fetchVippsAppConfig: (...args: unknown[]) => mockVippsConfig(...args) }
})

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { slug: 'durga-puja-2026' } }),
}))

import TicketPurchaseView from '../TicketPurchaseView.vue'
import { ValidationError } from '../../../services/ordersApi'

const baseEvent = { id: 1, title: 'Durga Puja 2026', slug: 'durga-puja-2026', published: true }
const baseTypes = {
  items: [
    { id: 1, name: 'Adult', description: null, price: 15000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, coupon_eligible: true, status: 'on_sale' },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  mockVippsConfig.mockResolvedValue({ enabled: false, surcharge_percent: 0 })
})

describe('TicketPurchaseView', () => {
  it('shows ticket types with formatted prices', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    expect(wrapper.text()).toContain('Adult')
    expect(wrapper.text()).toContain('150.00 kr')
  })

  it('shows multi-day tickets in a tab per day, all-days passes last, one day at a time', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, ticket_layout: 'tabs' })
    const t = baseTypes.items[0]
    mockFetchTicketTypes.mockResolvedValue({
      items: [
        { ...t, id: 1, name: 'Saturday Adult', valid_on: '2026-10-24' },
        { ...t, id: 2, name: 'Friday Adult', valid_on: '2026-10-23' },
        { ...t, id: 3, name: 'Weekend pass', valid_on: null },
      ],
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    expect(wrapper.findAll('.day-tab').map((b) => b.text())).toEqual(['Friday 23 Oct', 'Saturday 24 Oct', 'All days'])
    expect(wrapper.text()).toContain('Friday Adult')
    expect(wrapper.text()).not.toContain('Weekend pass')
    expect(wrapper.find('.next-day-nudge').text()).toContain('More happening on Saturday 24 Oct')
    await wrapper.find('.next-day-nudge').trigger('click')
    expect(wrapper.text()).toContain('Saturday Adult')
    expect(wrapper.find('.next-day-nudge').text()).toContain('Or get an all-days pass')
    await wrapper.find('.next-day-nudge').trigger('click')
    expect(wrapper.text()).toContain('Weekend pass')
    expect(wrapper.find('.next-day-nudge').exists()).toBe(false)
  })

  it('lists every day on one page under a heading per day when the layout is sections (the default)', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, ticket_layout: 'sections' })
    const t = baseTypes.items[0]
    mockFetchTicketTypes.mockResolvedValue({
      items: [
        { ...t, id: 1, name: 'Saturday Adult', valid_on: '2026-10-24' },
        { ...t, id: 2, name: 'Friday Adult', valid_on: '2026-10-23' },
        { ...t, id: 3, name: 'Weekend pass', valid_on: null },
      ],
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    expect(wrapper.find('.day-tab').exists()).toBe(false)
    expect(wrapper.findAll('.ticket-day-heading').map((h) => h.text())).toEqual(['Friday 23 Oct', 'Saturday 24 Oct', 'All days'])
    expect(wrapper.text()).toContain('Friday Adult')
    expect(wrapper.text()).toContain('Saturday Adult')
    expect(wrapper.text()).toContain('Weekend pass')
    expect(wrapper.find('.next-day-nudge').exists()).toBe(false)
  })

  it('shows a count on a day tab and a mobile review bar once tickets are chosen', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, ticket_layout: 'tabs' })
    const t = baseTypes.items[0]
    mockFetchTicketTypes.mockResolvedValue({
      items: [
        { ...t, id: 1, name: 'Saturday Adult', valid_on: '2026-10-24' },
        { ...t, id: 2, name: 'Friday Adult', valid_on: '2026-10-23' },
      ],
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()
    expect(wrapper.find('.mobile-order-bar').exists()).toBe(false)

    await wrapper.find('button[aria-label^="Increase"]').trigger('click')
    expect(wrapper.findAll('.day-tab')[0].text()).toContain('1')
    expect(wrapper.find('.mobile-order-bar').text()).toContain('1 ticket selected')
  })

  it('shows a flat list without tabs when no ticket type has a date', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    expect(wrapper.find('.day-tab').exists()).toBe(false)
    expect(wrapper.find('.ticket-day-heading').exists()).toBe(false)
  })

  it('does not show a Draft badge for a published event', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    expect(wrapper.text()).not.toContain('Draft')
  })

  it('shows a Draft badge and still lists ticket types when an admin previews an unpublished event', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, published: false })
    mockFetchTicketTypes.mockResolvedValue(baseTypes)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    expect(wrapper.text()).toContain('Draft')
    expect(wrapper.text()).toContain('Adult')
  })

  it('updates the running total as quantity increases', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(2)

    expect(wrapper.text()).toContain('300.00 kr')
  })

  it('submits checkout and shows the confirmation', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    mockCheckout.mockResolvedValue({
      id: 1,
      order_number: 'BCA-2026-000001',
      payment_status: 'pending',
      total_amount: 15000,
      items: [],
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 41234567')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).toHaveBeenCalledWith({
      event_id: 1,
      items: [{ ticket_type_id: 1, quantity: 1 }],
      customer_name: 'Priya Das',
      customer_email: 'priya@example.com',
      customer_phone: '+47 41234567',
    })
    expect(wrapper.text()).toContain('BCA-2026-000001')
  })

  it('requires a phone number, blocking submission client-side without calling the API', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Enter a valid phone number for Norway (+47, 8 digits).')
  })

  it('shows validation errors from the API', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    // A syntactically valid email/phone passes the client-side checks, so this still reaches
    // the (mocked) API — customer_name has no client-side check, only the server's.
    mockCheckout.mockRejectedValue(new ValidationError({ customer_name: 'This field is required.' }))

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 41234567')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('This field is required.')
  })

  it('also shows a server validation error near the Place order button, not just next to the field', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    mockCheckout.mockRejectedValue(
      new ValidationError({ customer_email: 'This email address can reserve at most 4 tickets for this event (0 remaining).' }),
    )

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 41234567')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    const submitButton = wrapper.find('button.submit-order')
    const summaryCard = submitButton.element.closest('aside')
    expect(summaryCard?.textContent).toContain('at most 4 tickets')
  })

  it('blocks submission client-side for a malformed email, without calling the API', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('not-an-email')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 41234567')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Enter a valid email address.')
  })

  it('blocks submission client-side for a phone number that is not 8 Norwegian digits', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 123')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Enter a valid phone number for Norway (+47, 8 digits).')
  })

  it('applies a valid coupon, shows the discount, and includes it at checkout', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    mockValidateCoupon.mockResolvedValue({ valid: true, code: 'SAVE20', discount_percent: 20 })
    mockCheckout.mockResolvedValue({
      id: 1,
      order_number: 'BCA-2026-000001',
      payment_status: 'pending',
      total_amount: 12000,
      coupon_code: 'SAVE20',
      discount_amount: 3000,
      items: [],
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="SAVE20"]').setValue('save20')
    const applyButton = wrapper.findAll('button').find((b) => b.text() === 'Apply')
    await applyButton?.trigger('click')
    await flushPromises()

    expect(mockValidateCoupon).toHaveBeenCalledWith(1, 'save20')
    expect(wrapper.text()).toContain('SAVE20')
    expect(wrapper.text()).toContain('20% off')
    expect(wrapper.text()).toContain('120.00 kr') // 150 - 20% = 120

    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 41234567')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).toHaveBeenCalledWith(
      expect.objectContaining({ coupon_code: 'SAVE20' }),
    )
    expect(wrapper.text()).toContain('Coupon SAVE20 applied')
  })

  it('shows an error for an invalid coupon and does not apply a discount', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    mockValidateCoupon.mockResolvedValue({ valid: false, error: 'Invalid or inactive coupon code.' })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[placeholder="SAVE20"]').setValue('NOPE')
    const applyButton = wrapper.findAll('button').find((b) => b.text() === 'Apply')
    await applyButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Invalid or inactive coupon code.')
  })

  it('shows the auto-issued tickets state instead of the Vipps panel when payment_status is paid', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    mockCheckout.mockResolvedValue({
      id: 1,
      order_number: 'BCA-2026-000001',
      payment_status: 'paid',
      order_status: 'confirmed',
      total_amount: 0,
      coupon_code: 'FREE100',
      discount_amount: 15000,
      customer_email: 'priya@example.com',
      items: [],
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 41234567')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Tickets issued!')
    expect(wrapper.text()).not.toContain('Pay with Vipps')
  })

  it('blocks submission when a coupon order exceeds the 2 adult + 2 child cap', async () => {
    const typesWithAges = {
      items: [
        { id: 1, name: 'Adult', description: null, price: 15000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, age_category: 'adult', coupon_eligible: true, status: 'on_sale' },
      ],
    }
    mockFetchEvent.mockResolvedValue({ ...baseEvent, coupon_max_adult: 2, coupon_max_child: 2 })
    mockFetchTicketTypes.mockResolvedValue(typesWithAges)
    mockValidateCoupon.mockResolvedValue({ valid: true, code: 'SAVE20', discount_percent: 20 })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(3)
    await wrapper.find('input[placeholder="SAVE20"]').setValue('SAVE20')
    const applyButton = wrapper.findAll('button').find((b) => b.text() === 'Apply')
    await applyButton?.trigger('click')
    await flushPromises()

    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('at most 2 adult and 2 child coupon-eligible tickets')
  })

  it('shows the per-email limit hint and blocks a quantity above it, only when the event sets one', async () => {
    const types = {
      items: [
        { id: 1, name: 'Adult', description: null, price: 15000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, age_category: 'adult', coupon_eligible: true, status: 'on_sale' },
      ],
    }
    mockFetchTicketTypes.mockResolvedValue(types)

    mockFetchEvent.mockResolvedValue(baseEvent)
    const unlimited = mount(TicketPurchaseView)
    await flushPromises()
    expect(unlimited.find('.email-limit-hint').exists()).toBe(false)

    mockFetchEvent.mockResolvedValue({ ...baseEvent, max_tickets_per_email: 4 })
    const limited = mount(TicketPurchaseView)
    await flushPromises()
    expect(limited.find('.email-limit-hint').text()).toContain('Up to 4 tickets')
    await limited.find('input[type="number"]').setValue(5)
    expect(limited.find('button.submit-order').attributes('disabled')).toBeDefined()
    expect(limited.text()).toContain('at most 4 tickets of each type')
  })

  it('discounts only the coupon-eligible ticket type in a mixed cart, charging the ineligible one in full', async () => {
    const mixedTypes = {
      items: [
        { id: 1, name: 'Adult', description: null, price: 15000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, coupon_eligible: true, status: 'on_sale' },
        { id: 2, name: 'VIP', description: null, price: 50000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, coupon_eligible: false, status: 'on_sale' },
      ],
    }
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(mixedTypes)
    mockValidateCoupon.mockResolvedValue({ valid: true, code: 'SAVE20', discount_percent: 20 })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    const qtyInputs = wrapper.findAll('input[type="number"]')
    await qtyInputs[0].setValue(1) // Adult, eligible: 150.00 kr
    await qtyInputs[1].setValue(1) // VIP, ineligible: 500.00 kr

    await wrapper.find('input[placeholder="SAVE20"]').setValue('SAVE20')
    const applyButton = wrapper.findAll('button').find((b) => b.text() === 'Apply')
    await applyButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Not eligible for the coupon discount — charged in full.')
    // Only the 150.00 kr Adult ticket is discounted 20% -> 30.00 kr off; the 500.00 kr VIP
    // ticket is untouched. Total = 150 + 500 - 30 = 620.00 kr.
    expect(wrapper.text()).toContain('-30.00 kr')
    expect(wrapper.text()).toContain('620.00 kr')
    expect(wrapper.text()).not.toContain('None of your selected ticket types are eligible')
  })

  it('respects a coupon restricted to specific ticket types even when both are coupon-eligible', async () => {
    const bothEligible = {
      items: [
        { id: 1, name: 'Adult', description: null, price: 15000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, coupon_eligible: true, status: 'on_sale' },
        { id: 2, name: 'Child', description: null, price: 5000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, coupon_eligible: true, status: 'on_sale' },
      ],
    }
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(bothEligible)
    // SANATAN only ever applies to Child (id 2) — Adult stays coupon_eligible but isn't allowed.
    mockValidateCoupon.mockResolvedValue({
      valid: true,
      code: 'SANATAN',
      discount_percent: 20,
      allowed_ticket_type_ids: [2],
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    const qtyInputs = wrapper.findAll('input[type="number"]')
    await qtyInputs[0].setValue(1) // Adult, coupon_eligible but not allowed by SANATAN
    await qtyInputs[1].setValue(1) // Child, allowed

    await wrapper.find('input[placeholder="SAVE20"]').setValue('SANATAN')
    const applyButton = wrapper.findAll('button').find((b) => b.text() === 'Apply')
    await applyButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Not eligible for the coupon discount — charged in full.')
    // Only the 50.00 kr Child ticket is discounted 20% -> 10.00 kr off; the 150.00 kr Adult
    // ticket is untouched despite being coupon_eligible. Total = 150 + 50 - 10 = 190.00 kr.
    expect(wrapper.text()).toContain('-10.00 kr')
    expect(wrapper.text()).toContain('190.00 kr')
  })

  it('warns and blocks submission when no selected ticket type is coupon-eligible', async () => {
    const ineligibleOnly = {
      items: [
        { id: 1, name: 'VIP', description: null, price: 50000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, coupon_eligible: false, status: 'on_sale' },
      ],
    }
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(ineligibleOnly)
    mockValidateCoupon.mockResolvedValue({ valid: true, code: 'SAVE20', discount_percent: 20 })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="SAVE20"]').setValue('SAVE20')
    const applyButton = wrapper.findAll('button').find((b) => b.text() === 'Apply')
    await applyButton?.trigger('click')
    await flushPromises()

    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('None of your selected ticket types are eligible for this coupon.')
    // The coupon banner must not claim success (green "applied") when it has zero effect on
    // the current cart — it should read as a neutral/warning notice instead.
    expect(wrapper.text()).not.toContain('Coupon SAVE20 applied (20% off).')
    expect(wrapper.text()).toContain("Coupon SAVE20 is valid but doesn't apply to your current selection.")
    const banner = wrapper.findAll('.ds-alert').find((el) => el.text().includes('SAVE20'))
    expect(banner?.classes()).toContain('ds-alert-warning')
    expect(banner?.classes()).not.toContain('ds-alert-success')
  })

  it('warns and blocks submission when the coupon has fewer redemptions left than requested', async () => {
    const oneType = {
      items: [
        { id: 1, name: 'Adult', description: null, price: 15000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, coupon_eligible: true, status: 'on_sale' },
      ],
    }
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(oneType)
    mockValidateCoupon.mockResolvedValue({
      valid: true,
      code: 'MEMBER',
      discount_percent: 100,
      remaining_redemptions: 0,
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(3)
    await wrapper.find('input[placeholder="SAVE20"]').setValue('MEMBER')
    const applyButton = wrapper.findAll('button').find((b) => b.text() === 'Apply')
    await applyButton?.trigger('click')
    await flushPromises()

    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).not.toHaveBeenCalled()
    // No false "applied (100% off)" success banner, no "-450.00 kr" discount preview, and no
    // "Free with this coupon" message — the coupon can't actually cover this cart.
    expect(wrapper.text()).not.toContain('Coupon MEMBER applied (100% off).')
    expect(wrapper.text()).toContain("Coupon MEMBER only has 0 use(s) left — you're requesting 3.")
    expect(wrapper.text()).not.toContain('Free with this coupon')
    expect(wrapper.text()).toContain('-0.00 kr')
    const banner = wrapper.findAll('.ds-alert').find((el) => el.text().includes('MEMBER'))
    expect(banner?.classes()).toContain('ds-alert-warning')
    expect(banner?.classes()).not.toContain('ds-alert-success')
  })

  it('blocks buying a child ticket with no adult ticket in the same order', async () => {
    const childOnly = {
      items: [
        { id: 1, name: 'Child', description: null, price: 5000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, age_category: 'child', coupon_eligible: true, status: 'on_sale' },
      ],
    }
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(childOnly)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 41234567')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain("A child ticket can't be purchased on its own")
  })

  it('allows a child ticket alongside an adult ticket', async () => {
    const adultAndChild = {
      items: [
        { id: 1, name: 'Adult', description: null, price: 15000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, age_category: 'adult', coupon_eligible: true, status: 'on_sale' },
        { id: 2, name: 'Child', description: null, price: 5000, capacity: null, remaining: null, sale_start: null, sale_end: null, members_only: false, age_category: 'child', coupon_eligible: true, status: 'on_sale' },
      ],
    }
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(adultAndChild)
    mockCheckout.mockResolvedValue({
      id: 1,
      order_number: 'BCA-2026-000001',
      payment_status: 'pending',
      total_amount: 20000,
      items: [],
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    const qtyInputs = wrapper.findAll('input[type="number"]')
    await qtyInputs[0].setValue(1)
    await qtyInputs[1].setValue(1)
    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 41234567')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).toHaveBeenCalled()
    expect(wrapper.text()).toContain('BCA-2026-000001')
  })

  it('offers Pay in the Vipps app with the fee, sends payment_method and redirects to Vipps', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    mockVippsConfig.mockResolvedValue({ enabled: true, surcharge_percent: 5 })
    mockCheckout.mockResolvedValue({ order_number: 'BCA-1', redirect_url: 'https://vipps.test/pay', items: [] })
    const hrefSet = vi.fn()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { set href(v: string) { hrefSet(v) } },
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()
    await wrapper.find('input[type="number"]').setValue(1)
    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 41234567')
    await wrapper.find('input[name="tp-pay"][value="app"]').setValue(true)

    expect(wrapper.find('.vipps-app-fee').text()).toContain('Convenience fee')
    expect(wrapper.find('.vipps-app-fee').text()).toContain('157.50 kr')

    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).toHaveBeenCalledWith(expect.objectContaining({ payment_method: 'vipps_app' }))
    expect(hrefSet).toHaveBeenCalledWith('https://vipps.test/pay')
  })

  it('follows the payment setting of the event: QR only hides the app option, App only shows the fee with no choice', async () => {
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    mockVippsConfig.mockResolvedValue({ enabled: true, surcharge_percent: 5 })

    const fill = async (wrapper: ReturnType<typeof mount>) => {
      await flushPromises()
      await wrapper.find('input[type="number"]').setValue(1)
    }

    mockFetchEvent.mockResolvedValue({ ...baseEvent, payment_methods: ['qr'] })
    let wrapper = mount(TicketPurchaseView)
    await fill(wrapper)
    expect(wrapper.find('input[name="tp-pay"]').exists()).toBe(false)
    expect(wrapper.find('.vipps-app-fee').exists()).toBe(false)

    mockFetchEvent.mockResolvedValue({ ...baseEvent, payment_methods: ['app'] })
    wrapper = mount(TicketPurchaseView)
    await fill(wrapper)
    expect(wrapper.find('input[name="tp-pay"]').exists()).toBe(false) // nothing to choose
    expect(wrapper.find('.vipps-app-fee').text()).toContain('157.50 kr')
    expect(wrapper.find('button.submit-order').text()).toContain('with Vipps')

    mockFetchEvent.mockResolvedValue({ ...baseEvent, payment_methods: ['qr', 'app'] })
    wrapper = mount(TicketPurchaseView)
    await fill(wrapper)
    expect(wrapper.findAll('input[name="tp-pay"]')).toHaveLength(2)
  })

  it('offers Cash, shows the admin-written wording, sends payment_method cash and then shows the cash panel', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, payment_methods: ['qr', 'cash'], cash_note: 'Your place is not confirmed until you pay.' })
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    mockVippsConfig.mockResolvedValue({ enabled: false, surcharge_percent: 0 })
    mockCheckout.mockResolvedValue({
      order_number: 'BCA-2026-000009', customer_email: 'priya@example.com', total_amount: 15000, payment_status: 'pending',
      payment_method: 'cash', cash_note: 'Your place is not confirmed until you pay.', discount_amount: 0, coupon_code: null, items: [],
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()
    await wrapper.find('input[type="number"]').setValue(1)
    expect(wrapper.find('input[name="tp-pay"][value="app"]').exists()).toBe(false) // not on offer for this event
    await wrapper.find('input[name="tp-pay"][value="cash"]').setValue(true)
    expect(wrapper.find('.cash-note-preview').text()).toContain('not confirmed until you pay')

    await wrapper.find('input[placeholder="Full name"]').setValue('Priya Das')
    await wrapper.find('input[placeholder="Email address"]').setValue('priya@example.com')
    await wrapper.find('input[placeholder="Phone"]').setValue('+47 41234567')
    await wrapper.find('button.submit-order').trigger('click')
    await flushPromises()

    expect(mockCheckout).toHaveBeenCalledWith(expect.objectContaining({ payment_method: 'cash' }))
    expect(wrapper.find('.cash-panel').exists()).toBe(true)
    expect(wrapper.find('.cash-panel').text()).toContain('not confirmed until you pay')
    expect(wrapper.text()).not.toContain('I have paid')
  })

  it('a cash-only event has nothing to choose but still shows the wording and orders with cash', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, payment_methods: ['cash'], cash_note: 'Pay at the door.' })
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    mockVippsConfig.mockResolvedValue({ enabled: false, surcharge_percent: 0 })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()
    await wrapper.find('input[type="number"]').setValue(1)
    expect(wrapper.find('input[name="tp-pay"]').exists()).toBe(false)
    expect(wrapper.find('.cash-note-preview').text()).toContain('Pay at the door.')
  })

  it('says ticket sales have closed (and offers no ticket form) once the event cut-off has passed', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, sales_closed: true })
    mockFetchTicketTypes.mockResolvedValue(baseTypes)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    expect(wrapper.find('.sales-closed').text()).toContain('Ticket sales for this event have closed.')
    expect(wrapper.find('button.submit-order').exists()).toBe(false)
  })

  it('says when ticket sales open (and offers no ticket form) before the event start time', async () => {
    mockFetchEvent.mockResolvedValue({ ...baseEvent, sales_not_open: true, sales_open_at: '2099-01-02T10:00:00Z' })
    mockFetchTicketTypes.mockResolvedValue(baseTypes)

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    expect(wrapper.find('.sales-not-open').text()).toContain('Ticket sales open')
    expect(wrapper.find('button.submit-order').exists()).toBe(false)
  })

  it('tells the buyer why a ticket type cannot be bought (closed, sold out, not open yet)', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue({
      items: [
        { ...baseTypes.items[0], id: 1, name: 'Dinner', status: 'ended' },
        { ...baseTypes.items[0], id: 2, name: 'Lunch', status: 'sold_out' },
        { ...baseTypes.items[0], id: 3, name: 'Brunch', status: 'upcoming', sale_start: '2030-01-01T10:00:00Z' },
        { ...baseTypes.items[0], id: 4, name: 'Adult', status: 'on_sale' },
      ],
    })

    const wrapper = mount(TicketPurchaseView)
    await flushPromises()

    // each unavailable ticket gets a small pill beside its name — no banner, so the card keeps its height
    expect(wrapper.find('.type-closed-banner').exists()).toBe(false)
    const pills = wrapper.findAll('.type-pill')
    expect(pills).toHaveLength(3)
    expect(pills[0].text()).toBe('Sales closed')
    expect(pills[0].classes()).toContain('ds-badge-warning')
    expect(pills[1].text()).toBe('Sold out')
    expect(pills[2].text()).toMatch(/^Opens /)
  })
})

describe('TicketPurchaseView intro (W6-R73)', () => {
  it('does not promise Vipps: the payment choices below say what this square accepts', async () => {
    mockFetchEvent.mockResolvedValue(baseEvent)
    mockFetchTicketTypes.mockResolvedValue(baseTypes)
    const wrapper = mount(TicketPurchaseView)
    await flushPromises()
    expect(wrapper.text()).toContain('Choose your tickets and pay')
    expect(wrapper.find('.ds-intro').text()).not.toContain('Vipps')
  })
})
