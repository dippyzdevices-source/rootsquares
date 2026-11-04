// Tests for AdminEventFormView (62 cases), e.g. AdminEventFormView ticket types; loads and displays existing ticket types; shows the active coupons that can discount each ticket type as pills.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chooseOption } from '../../../test-utils/baseSelect'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { defineComponent } from 'vue'

const mockFetchAdminEvent = vi.fn()
const mockFetchAdminTicketTypes = vi.fn()
const mockCreateAdminTicketType = vi.fn()
const mockFetchAdminCoupons = vi.fn()
const mockCreateAdminCoupon = vi.fn()
const mockUpdateAdminCoupon = vi.fn()
const mockCreateEventSession = vi.fn()
const mockCreateTaskAssignment = vi.fn()
const mockUpdateTaskAssignment = vi.fn()
const mockDeleteTaskAssignment = vi.fn()
const mockFetchAdminMembers = vi.fn()

const mockUploadEventBanner = vi.fn()
const mockUpdateAdminEvent = vi.fn()
const mockAddEventBanner = vi.fn()
const mockDeleteEventBanner = vi.fn()

vi.mock('../../../services/eventSeriesApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/eventSeriesApi')>()),
  fetchEventSeries: vi.fn().mockResolvedValue({ series: null }),
}))
vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: vi.fn(async (key: string) =>
    key === 'task_category'
      ? [
          { value: 'food', label: 'Food' },
          { value: 'cultural', label: 'Cultural' },
          { value: 'decoration', label: 'Decoration' },
          { value: 'other', label: 'Other' },
        ]
      : [
          { value: 'festival', label: 'Festival' },
          { value: 'cultural', label: 'Cultural' },
          { value: 'community', label: 'Community' },
          { value: 'other', label: 'Other' },
        ],
  ),
}))

vi.mock('../../../services/adminEventsApi', () => ({
  fetchAdminEvent: (...args: unknown[]) => mockFetchAdminEvent(...args),
  createAdminEvent: vi.fn(),
  updateAdminEvent: (...args: unknown[]) => mockUpdateAdminEvent(...args),
  uploadEventBanner: (...args: unknown[]) => mockUploadEventBanner(...args),
  addEventBanner: (...args: unknown[]) => mockAddEventBanner(...args),
  deleteEventBanner: (...args: unknown[]) => mockDeleteEventBanner(...args),
  ValidationError: class extends Error {},
}))

vi.mock('../../../services/adminEventSessionsApi', () => ({
  createEventSession: (...args: unknown[]) => mockCreateEventSession(...args),
  updateEventSession: vi.fn(),
  deleteEventSession: vi.fn(),
  ValidationError: class extends Error {},
}))

vi.mock('../../../services/adminTicketTypesApi', () => ({
  fetchAdminTicketTypes: (...args: unknown[]) => mockFetchAdminTicketTypes(...args),
  createAdminTicketType: (...args: unknown[]) => mockCreateAdminTicketType(...args),
  updateAdminTicketType: vi.fn(),
  deleteAdminTicketType: vi.fn(),
  ValidationError: class extends Error {},
}))

vi.mock('../../../services/couponsApi', () => ({
  fetchAdminCoupons: (...args: unknown[]) => mockFetchAdminCoupons(...args),
  createAdminCoupon: (...args: unknown[]) => mockCreateAdminCoupon(...args),
  updateAdminCoupon: (...args: unknown[]) => mockUpdateAdminCoupon(...args),
  ValidationError: class extends Error {},
}))

vi.mock('../../../services/adminEventTaskAssignmentsApi', () => ({
  createTaskAssignment: (...args: unknown[]) => mockCreateTaskAssignment(...args),
  updateTaskAssignment: (...args: unknown[]) => mockUpdateTaskAssignment(...args),
  deleteTaskAssignment: (...args: unknown[]) => mockDeleteTaskAssignment(...args),
  ValidationError: class extends Error {},
}))

vi.mock('../../../services/adminMembersApi', () => ({
  fetchAdminMembers: (...args: unknown[]) => mockFetchAdminMembers(...args),
}))

// Real Tiptap needs a live DOM contenteditable and its own dedicated tests (see
// RichTextEditor.spec.ts) — stubbed here as a plain textarea so this file can test
// AdminEventFormView's own v-model wiring in isolation, same as AdminNewsFormView.spec.ts.
vi.mock('../../../components/ui/RichTextEditor.vue', () => ({
  default: defineComponent({
    props: ['modelValue', 'label'],
    emits: ['update:modelValue'],
    template: '<textarea :value="modelValue" @input="onInput" />',
    methods: {
      onInput(event: Event) {
        this.$emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
      },
    },
  }),
}))

// Which modules are off in a test (W8-R21, W8-R23): none by default
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', async (importOriginal) => ({ ...(await importOriginal<typeof import('../../../services/modules')>()), moduleEnabled: (key?: string) => !off.keys.includes(key ?? '') }))

import AdminEventFormView from '../AdminEventFormView.vue'

async function mountAtEventId(id: string, tab?: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/events/:id', component: AdminEventFormView },
      { path: '/admin/events', component: { template: '<div />' } },
    ],
  })
  router.push(`/admin/events/${id}`)
  await router.isReady()
  const wrapper = mount(AdminEventFormView, { global: { plugins: [router] } })
  if (tab) {
    await flushPromises()
    await wrapper.findAll('.event-tabs .ds-tab').find((b) => b.text() === tab)!.trigger('click')
  }
  return wrapper
}

async function mountAtNew() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/events/new', component: AdminEventFormView },
      { path: '/admin/events', component: { template: '<div />' } },
    ],
  })
  router.push('/admin/events/new')
  await router.isReady()
  return mount(AdminEventFormView, { global: { plugins: [router] } })
}

beforeEach(() => {
  vi.clearAllMocks()
  off.keys = []
  mockFetchAdminEvent.mockResolvedValue({
    id: 1,
    title: 'Durga Puja',
    slug: 'durga-puja',
    event_type: 'festival',
    short_description: null,
    description: null,
    start_datetime: '2099-10-01T10:00:00Z',
    end_datetime: null,
    venue: null,
    address: null,
    capacity: null,
    banner_image: null,
    published: true,
    sessions: [],
    task_assignments: [],
  })
  mockFetchAdminTicketTypes.mockResolvedValue({
    items: [{ id: 1, event_id: 1, name: 'Adult', description: null, price: 15000, capacity: null, sold: 0, sale_start: null, sale_end: null, members_only: false, age_category: 'other', sort_order: 0 }],
  })
  mockFetchAdminCoupons.mockResolvedValue({ items: [] })
})

describe('AdminEventFormView ticket types', () => {
  it('loads and displays existing ticket types', async () => {
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()

    expect(mockFetchAdminTicketTypes).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('Adult')
  })

  it('shows the active coupons that can discount each ticket type as pills', async () => {
    const type = (id: number, name: string, eligible: boolean) => ({
      id, event_id: 1, name, description: null, price: 15000, capacity: null, sold: 0, sale_start: null, sale_end: null,
      valid_on: null, members_only: false, age_category: 'other', coupon_eligible: eligible, sort_order: id,
    })
    const coupon = (id: number, code: string, allowed: number[], active = true) => ({
      id, event_id: 1, code, discount_percent: 20, is_active: active, allowed_ticket_type_ids: allowed,
      max_redemptions: null, redemption_count: 0,
    })
    mockFetchAdminTicketTypes.mockResolvedValue({ items: [type(1, 'Adult', true), type(2, 'Child', true), type(3, 'VIP', false)] })
    mockFetchAdminCoupons.mockResolvedValue({
      items: [coupon(1, 'GENERAL', []), coupon(2, 'CHILDONLY', [2]), coupon(3, 'RETIRED', [], false)],
    })
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()

    const pillsOf = (name: string) =>
      wrapper.findAll('tbody tr').find((tr) => tr.text().startsWith(name))!.findAll('.ds-badge-accent').map((b) => b.text())
    expect(pillsOf('Adult')).toEqual(['GENERAL · 20%'])
    expect(pillsOf('Child')).toEqual(['GENERAL · 20%', 'CHILDONLY · 20%'])
    expect(pillsOf('VIP')).toEqual([]) // not coupon-eligible
  })

  it('sections ticket types by their valid-on day', async () => {
    mockFetchAdminTicketTypes.mockResolvedValue({
      items: [
        { id: 1, event_id: 1, name: 'Saturday Adult', description: null, price: 15000, capacity: null, sold: 0, sale_start: null, sale_end: null, valid_on: '2026-10-24', members_only: false, age_category: 'other', sort_order: 0 },
        { id: 2, event_id: 1, name: 'Friday Adult', description: null, price: 15000, capacity: null, sold: 0, sale_start: null, sale_end: null, valid_on: '2026-10-23', members_only: false, age_category: 'other', sort_order: 1 },
      ],
    })
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()

    expect(wrapper.findAll('.ticket-day-row').map((r) => r.text())).toEqual(['Friday 23 Oct', 'Saturday 24 Oct'])
    wrapper.unmount()
  })

  it('duplicates a ticket type as a copy with the next sort order', async () => {
    mockCreateAdminTicketType.mockResolvedValue({ id: 9 })
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()

    await wrapper.find('button[aria-label="Duplicate Adult"]').trigger('click')
    await flushPromises()

    const [eventId, payload] = mockCreateAdminTicketType.mock.calls[0] as [number, Record<string, unknown>]
    expect(eventId).toBe(1)
    expect(payload).toMatchObject({ name: 'Adult' })
    expect(payload.sort_order).toBeGreaterThanOrEqual(1)
    expect(mockFetchAdminTicketTypes).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })

  it('requires an age group, starting blank, before a ticket type can be saved', async () => {
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()
    mockCreateAdminTicketType.mockClear()

    await wrapper.find('button.add-ticket-type').trigger('click')
    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="Adult"]').setValue('Dinner')
    await body.findAll('input[type="number"]')[0].setValue('50.00')
    await body.find('button.save-ticket-type').trigger('click')
    await flushPromises()

    expect(mockCreateAdminTicketType).not.toHaveBeenCalled()
    expect(body.text()).toContain('Choose an age group.')
    wrapper.unmount()
  })

  it('on a multi-day event, requires a Valid on day and sends null for All days', async () => {
    mockFetchAdminEvent.mockResolvedValue({ ...(await mockFetchAdminEvent()), start_datetime: '2099-10-23T12:00:00Z', end_datetime: '2099-10-25T12:00:00Z' })
    mockCreateAdminTicketType.mockResolvedValue({ id: 5 })
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()
    await wrapper.find('button.add-ticket-type').trigger('click')
    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="Adult"]').setValue('Weekend pass')
    await body.findAll('input[type="number"]')[0].setValue('600.00')
    await chooseOption(body, 'adult')
    await body.find('button.save-ticket-type').trigger('click')
    await flushPromises()

    expect(mockCreateAdminTicketType).not.toHaveBeenCalled()
    expect(body.text()).toContain('Choose the day, or All days.')

    await chooseOption(body, 'ALL', 1)
    await body.find('button.save-ticket-type').trigger('click')
    await flushPromises()
    expect(mockCreateAdminTicketType).toHaveBeenCalledWith(1, expect.objectContaining({ valid_on: null }))
    wrapper.unmount()
  })

  it('creates a new ticket type via the modal', async () => {
    mockCreateAdminTicketType.mockResolvedValue({
      id: 2,
      event_id: 1,
      name: 'Child',
      description: null,
      price: 5000,
      capacity: null,
      sold: 0,
      sale_start: null,
      sale_end: null,
      members_only: false,
      sort_order: 1,
    })
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()

    await wrapper.find('button.add-ticket-type').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="Adult"]').setValue('Child')
    await body.findAll('input[type="number"]')[0].setValue('50.00')
    await chooseOption(body, 'adult')
    await body.find('button.save-ticket-type').trigger('click')
    await flushPromises()

    expect(mockCreateAdminTicketType).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ name: 'Child', price: 5000 }),
    )

    wrapper.unmount()
  })

  it('includes the description in the ticket type payload', async () => {
    mockCreateAdminTicketType.mockResolvedValue({
      id: 2,
      event_id: 1,
      name: 'Child',
      description: 'Includes a meal.',
      price: 5000,
      capacity: null,
      sold: 0,
      sale_start: null,
      sale_end: null,
      members_only: false,
      sort_order: 1,
    })
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()

    await wrapper.find('button.add-ticket-type').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="Adult"]').setValue('Child')
    await body.find('textarea').setValue('Includes a meal.')
    await body.findAll('input[type="number"]')[0].setValue('50.00')
    await chooseOption(body, 'adult')
    await body.find('button.save-ticket-type').trigger('click')
    await flushPromises()

    expect(mockCreateAdminTicketType).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ description: 'Includes a meal.' }),
    )

    wrapper.unmount()
  })

  it('includes the chosen age category in the ticket type payload', async () => {
    mockCreateAdminTicketType.mockResolvedValue({
      id: 2,
      event_id: 1,
      name: 'Child',
      description: null,
      price: 5000,
      capacity: null,
      sold: 0,
      sale_start: null,
      sale_end: null,
      members_only: false,
      age_category: 'child',
      sort_order: 1,
    })
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()

    await wrapper.find('button.add-ticket-type').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="Adult"]').setValue('Child')
    await body.findAll('input[type="number"]')[0].setValue('50.00')
    await chooseOption(body, 'child')
    await body.find('button.save-ticket-type').trigger('click')
    await flushPromises()

    expect(mockCreateAdminTicketType).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ age_category: 'child' }),
    )

    wrapper.unmount()
  })

  it('saves a sales window for one ticket type (open from / close at)', async () => {
    mockCreateAdminTicketType.mockResolvedValue({ id: 3, event_id: 1, name: 'Dinner', description: null, price: 20000, capacity: null, sold: 0, sale_start: null, sale_end: null, members_only: false, age_category: 'other', sort_order: 1 })
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()
    await wrapper.find('button.add-ticket-type').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="Adult"]').setValue('Dinner')
    await body.findAll('input[type="number"]')[0].setValue('200.00')
    await body.find('input[aria-label="Sales close at"]').setValue('2026-10-09T18:00')
    await chooseOption(body, 'adult')
    await body.find('button.save-ticket-type').trigger('click')
    await flushPromises()

    expect(mockCreateAdminTicketType).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ sale_start: null, sale_end: expect.stringMatching(/^2026-10-09T/) }),
    )
    wrapper.unmount()
  })

  it('defaults a new ticket type to coupon-eligible, and can be unchecked', async () => {
    mockCreateAdminTicketType.mockResolvedValue({
      id: 2,
      event_id: 1,
      name: 'VIP',
      description: null,
      price: 50000,
      capacity: null,
      sold: 0,
      sale_start: null,
      sale_end: null,
      members_only: false,
      age_category: 'other',
      coupon_eligible: false,
      sort_order: 1,
    })
    const wrapper = await mountAtEventId('1', 'Tickets')
    await flushPromises()

    await wrapper.find('button.add-ticket-type').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="Adult"]').setValue('VIP')
    await body.findAll('input[type="number"]')[0].setValue('500.00')
    const checkboxes = body.findAll('input[type="checkbox"]')
    expect((checkboxes[1].element as HTMLInputElement).checked).toBe(true) // coupon_eligible defaults on
    await checkboxes[1].setValue(false)
    await chooseOption(body, 'adult')
    await body.find('button.save-ticket-type').trigger('click')
    await flushPromises()

    expect(mockCreateAdminTicketType).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ coupon_eligible: false }),
    )

    wrapper.unmount()
  })
})

describe('AdminEventFormView coupons', () => {
  it('loads and displays existing coupons', async () => {
    mockFetchAdminCoupons.mockResolvedValue({
      items: [{ id: 1, event_id: 1, code: 'SAVE20', discount_percent: 20, is_active: true, allowed_ticket_type_ids: [], max_redemptions: null, redemption_count: 0 }],
    })
    const wrapper = await mountAtEventId('1', 'Coupons')
    await flushPromises()

    expect(mockFetchAdminCoupons).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('SAVE20')
    expect(wrapper.text()).toContain('20%')
  })

  it('creates a new coupon via the modal, upper-casing the code', async () => {
    mockCreateAdminCoupon.mockResolvedValue({
      id: 1,
      event_id: 1,
      code: 'SAVE20',
      discount_percent: 20,
      is_active: true,
      allowed_ticket_type_ids: [],
      max_redemptions: null,
      redemption_count: 0,
    })
    const wrapper = await mountAtEventId('1', 'Coupons')
    await flushPromises()

    await wrapper.find('button.add-coupon').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="SAVE20"]').setValue('save20')
    await body.find('input[type="number"]').setValue('20')
    await body.find('button.save-coupon').trigger('click')
    await flushPromises()

    expect(mockCreateAdminCoupon).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ code: 'save20', discount_percent: 20 }),
    )

    wrapper.unmount()
  })

  it('restricts a coupon to selected ticket types via pill toggles', async () => {
    mockFetchAdminTicketTypes.mockResolvedValue({
      items: [
        { id: 1, event_id: 1, name: 'Adult', description: null, price: 15000, capacity: null, sold: 0, sale_start: null, sale_end: null, members_only: false, age_category: 'adult', sort_order: 0 },
        { id: 2, event_id: 1, name: 'Child', description: null, price: 5000, capacity: null, sold: 0, sale_start: null, sale_end: null, members_only: false, age_category: 'child', sort_order: 1 },
      ],
    })
    mockCreateAdminCoupon.mockResolvedValue({
      id: 1,
      event_id: 1,
      code: 'SANATAN',
      discount_percent: 20,
      is_active: true,
      allowed_ticket_type_ids: [2],
      max_redemptions: null,
      redemption_count: 0,
    })
    const wrapper = await mountAtEventId('1', 'Coupons')
    await flushPromises()

    await wrapper.find('button.add-coupon').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="SAVE20"]').setValue('sanatan')
    await body.find('input[type="number"]').setValue('20')
    const pills = body.findAll('button.coupon-ticket-type-pill')
    expect(pills).toHaveLength(2)
    await pills[1].trigger('click') // select "Child" only
    await body.find('button.save-coupon').trigger('click')
    await flushPromises()

    expect(mockCreateAdminCoupon).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ allowed_ticket_type_ids: [2] }),
    )

    wrapper.unmount()
  })

  it('shows which ticket types a coupon applies to', async () => {
    mockFetchAdminTicketTypes.mockResolvedValue({
      items: [
        { id: 1, event_id: 1, name: 'Adult', description: null, price: 15000, capacity: null, sold: 0, sale_start: null, sale_end: null, members_only: false, age_category: 'adult', sort_order: 0 },
        { id: 2, event_id: 1, name: 'Child', description: null, price: 5000, capacity: null, sold: 0, sale_start: null, sale_end: null, members_only: false, age_category: 'child', sort_order: 1 },
      ],
    })
    mockFetchAdminCoupons.mockResolvedValue({
      items: [
        { id: 1, event_id: 1, code: 'MEMBER', discount_percent: 10, is_active: true, allowed_ticket_type_ids: [], max_redemptions: null, redemption_count: 0 },
        { id: 2, event_id: 1, code: 'SANATAN', discount_percent: 20, is_active: true, allowed_ticket_type_ids: [2], max_redemptions: 50, redemption_count: 3 },
      ],
    })

    const wrapper = await mountAtEventId('1', 'Coupons')
    await flushPromises()

    expect(wrapper.text()).toContain('All ticket types')
    expect(wrapper.text()).toContain('Child')
    // The "Uses" column reflects redemption_count / max_redemptions per coupon.
    expect(wrapper.text()).toContain('3 / 50')
  })

  it('toggles a coupon between active and inactive', async () => {
    mockFetchAdminCoupons.mockResolvedValue({
      items: [{ id: 1, event_id: 1, code: 'SAVE20', discount_percent: 20, is_active: true, allowed_ticket_type_ids: [], max_redemptions: null, redemption_count: 0 }],
    })
    mockUpdateAdminCoupon.mockResolvedValue({
      id: 1,
      event_id: 1,
      code: 'SAVE20',
      discount_percent: 20,
      is_active: false,
      allowed_ticket_type_ids: [],
      max_redemptions: null,
      redemption_count: 0,
    })
    const wrapper = await mountAtEventId('1', 'Coupons')
    await flushPromises()

    await wrapper.find('button[aria-label="Deactivate SAVE20"]').trigger('click')
    await flushPromises()

    expect(mockUpdateAdminCoupon).toHaveBeenCalledWith(1, { is_active: false })
  })

  it('sets a redemption limit on a new coupon', async () => {
    mockCreateAdminCoupon.mockResolvedValue({
      id: 1,
      event_id: 1,
      code: 'SAVE20',
      discount_percent: 20,
      is_active: true,
      allowed_ticket_type_ids: [],
      max_redemptions: 50,
      redemption_count: 0,
    })
    const wrapper = await mountAtEventId('1', 'Coupons')
    await flushPromises()

    await wrapper.find('button.add-coupon').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="SAVE20"]').setValue('save20')
    await body.find('input[type="number"]').setValue('20')
    await body.find('input[placeholder="e.g. 50"]').setValue('50')
    await body.find('button.save-coupon').trigger('click')
    await flushPromises()

    expect(mockCreateAdminCoupon).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ max_redemptions: 50 }),
    )

    wrapper.unmount()
  })

  it('leaves the redemption limit unlimited (null) when the field is left blank', async () => {
    mockCreateAdminCoupon.mockResolvedValue({
      id: 1,
      event_id: 1,
      code: 'SAVE20',
      discount_percent: 20,
      is_active: true,
      allowed_ticket_type_ids: [],
      max_redemptions: null,
      redemption_count: 0,
    })
    const wrapper = await mountAtEventId('1', 'Coupons')
    await flushPromises()

    await wrapper.find('button.add-coupon').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[placeholder="SAVE20"]').setValue('save20')
    await body.find('input[type="number"]').setValue('20')
    await body.find('button.save-coupon').trigger('click')
    await flushPromises()

    expect(mockCreateAdminCoupon).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ max_redemptions: null }),
    )

    wrapper.unmount()
  })
})

describe('AdminEventFormView volunteer assignments', () => {
  it('displays existing volunteer assignments', async () => {
    mockFetchAdminEvent.mockResolvedValue({
      id: 1,
      title: 'Durga Puja',
      slug: 'durga-puja',
      event_type: 'festival',
      short_description: null,
      description: null,
      start_datetime: '2026-10-01T10:00:00Z',
      end_datetime: null,
      venue: null,
      address: null,
      capacity: null,
      banner_image: null,
      published: true,
      sessions: [],
      task_assignments: [{ id: 1, member_id: 5, member_name: 'Priya Das', category: 'food' }],
    })

    const wrapper = await mountAtEventId('1', 'Volunteers')
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('Food')

    wrapper.unmount()
  })

  it('assigns a volunteer by picking one from the dropdown and a category', async () => {
    mockFetchAdminMembers.mockResolvedValue({
      items: [{ id: 5, name: 'Priya Das', email: 'priya@example.com', phone: null, latest_membership: null }],
      page: 1, per_page: 100, total: 1, total_pages: 1,
    })
    mockCreateTaskAssignment.mockResolvedValue({
      id: 1, member_id: 5, member_name: 'Priya Das', category: 'food',
    })

    const wrapper = await mountAtEventId('1', 'Volunteers')
    await flushPromises()

    await wrapper.find('button.add-task-assignment').trigger('click')
    await flushPromises()

    expect(mockFetchAdminMembers).toHaveBeenCalledWith('', 'volunteer')

    const body = new DOMWrapper(document.body)
    expect(body.findAll('input').length).toBe(0)

    await body.find('button.volunteer-picker-trigger').trigger('click')
    expect(body.text()).toContain('priya@example.com')
    const volunteerRow = body.findAll('.ds-account-menu-row').find((r) => r.text().includes('Priya Das'))!
    await volunteerRow.trigger('click')

    await chooseOption(body, 'food')

    await body.find('button.save-task-assignment').trigger('click')
    await flushPromises()

    expect(mockCreateTaskAssignment).toHaveBeenCalledWith(1, { member_id: 5, category: 'food' })

    wrapper.unmount()
  })

  it('edits an existing assignment\'s category without re-selecting the member', async () => {
    mockFetchAdminTicketTypes.mockResolvedValue({ items: [] })
    mockFetchAdminEvent.mockResolvedValue({
      id: 1,
      title: 'Durga Puja',
      slug: 'durga-puja',
      event_type: 'festival',
      short_description: null,
      description: null,
      start_datetime: '2026-10-01T10:00:00Z',
      end_datetime: null,
      venue: null,
      address: null,
      capacity: null,
      banner_image: null,
      published: true,
      sessions: [],
      task_assignments: [{ id: 1, member_id: 5, member_name: 'Priya Das', category: 'food' }],
    })
    mockUpdateTaskAssignment.mockResolvedValue({
      id: 1, member_id: 5, member_name: 'Priya Das', category: 'decoration',
    })

    const wrapper = await mountAtEventId('1', 'Volunteers')
    await flushPromises()

    const editButton = wrapper.find('button[aria-label="Edit Priya Das"]')
    await editButton.trigger('click')

    const body = new DOMWrapper(document.body)
    expect(body.text()).toContain('Priya Das')
    await chooseOption(body, 'decoration')
    await body.find('button.save-task-assignment').trigger('click')
    await flushPromises()

    expect(mockUpdateTaskAssignment).toHaveBeenCalledWith(1, 1, { category: 'decoration' })

    wrapper.unmount()
  })

  it('removes a volunteer assignment', async () => {
    mockFetchAdminTicketTypes.mockResolvedValue({ items: [] })
    mockFetchAdminEvent.mockResolvedValue({
      id: 1,
      title: 'Durga Puja',
      slug: 'durga-puja',
      event_type: 'festival',
      short_description: null,
      description: null,
      start_datetime: '2026-10-01T10:00:00Z',
      end_datetime: null,
      venue: null,
      address: null,
      capacity: null,
      banner_image: null,
      published: true,
      sessions: [],
      task_assignments: [{ id: 1, member_id: 5, member_name: 'Priya Das', category: 'food' }],
    })
    mockDeleteTaskAssignment.mockResolvedValue(undefined)

    const wrapper = await mountAtEventId('1', 'Volunteers')
    await flushPromises()

    const removeButton = wrapper.find('button[aria-label="Remove Priya Das"]')
    await removeButton.trigger('click')
    await flushPromises()

    expect(mockDeleteTaskAssignment).toHaveBeenCalledWith(1, 1)

    wrapper.unmount()
  })
})

// Regression test for a previously-reported live-browser bug ("schedule table doesn't refresh
// after adding an item until a manual reload"). This test proves the component's own
// save->reload->re-render path is correct in isolation with two distinct mocked API responses —
// it could not be reproduced at the component level, which points to something outside this
// component's code (most likely transient read-after-write lag against the live Neon DB, since
// the report itself noted the item "saves correctly server-side"). Kept as a standing regression
// test for this exact refresh path regardless.
describe('AdminEventFormView schedule', () => {
  it('shows a newly added schedule item in the table without a manual reload', async () => {
    mockCreateEventSession.mockResolvedValue({
      id: 1,
      day_label: '2026-10-09',
      time: '18:00',
      title: 'Cultural Programme',
      description: null,
      sort_order: 0,
    })
    // Second fetchAdminEvent call (post-save reload) returns the event WITH the new session.
    mockFetchAdminEvent.mockResolvedValueOnce({
      id: 1,
      title: 'Durga Puja',
      slug: 'durga-puja',
      event_type: 'festival',
      short_description: null,
      description: null,
      start_datetime: '2026-10-01T10:00:00Z',
      end_datetime: null,
      venue: null,
      address: null,
      capacity: null,
      banner_image: null,
      published: true,
      sessions: [],
      task_assignments: [],
    })
    mockFetchAdminEvent.mockResolvedValueOnce({
      id: 1,
      title: 'Durga Puja',
      slug: 'durga-puja',
      event_type: 'festival',
      short_description: null,
      description: null,
      start_datetime: '2026-10-01T10:00:00Z',
      end_datetime: null,
      venue: null,
      address: null,
      capacity: null,
      banner_image: null,
      published: true,
      sessions: [{ id: 1, day_label: 'Friday', time: '18:00', title: 'Cultural Programme', description: null, sort_order: 0 }],
      task_assignments: [],
    })

    const wrapper = await mountAtEventId('1', 'Schedule')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Cultural Programme')

    const addButton = wrapper.findAll('button').find((b) => b.text() === 'Add schedule item')!
    await addButton.trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[type="date"]').setValue('2026-10-09')
    await body.find('input[type="time"]').setValue('18:00')
    await body.find('input[placeholder="Cultural Programme"]').setValue('Cultural Programme')
    const saveButton = body.findAll('button').find((b) => b.text() === 'Save')!
    await saveButton.trigger('click')
    await flushPromises()

    expect(mockFetchAdminEvent).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Cultural Programme')

    wrapper.unmount()
  })

  it('includes the description in the schedule item payload', async () => {
    mockCreateEventSession.mockResolvedValue({
      id: 1,
      day_label: '2026-10-09',
      time: '18:00',
      title: 'Cultural Programme',
      description: 'Traditional dance and music.',
      sort_order: 0,
    })
    const wrapper = await mountAtEventId('1', 'Schedule')
    await flushPromises()

    const addButton = wrapper.findAll('button').find((b) => b.text() === 'Add schedule item')!
    await addButton.trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input[type="date"]').setValue('2026-10-09')
    await body.find('input[type="time"]').setValue('18:00')
    await body.find('input[placeholder="Cultural Programme"]').setValue('Cultural Programme')
    await body.find('textarea').setValue('Traditional dance and music.')
    const saveButton = body.findAll('button').find((b) => b.text() === 'Save')!
    await saveButton.trigger('click')
    await flushPromises()

    expect(mockCreateEventSession).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ description: 'Traditional dance and music.' }),
    )

    wrapper.unmount()
  })
})

describe('AdminEventFormView ticket layout', () => {
  it('defaults to sections on the Sales tab and saves the chosen layout', async () => {
    const wrapper = await mountAtEventId('1', 'Sales')
    await flushPromises()
    const radios = wrapper.findAll('input[name="ticket-layout"]')
    expect(radios.map((r) => (r.element as HTMLInputElement).checked)).toEqual([true, false])

    await radios[1].setValue()
    await wrapper.find('button.ds-btn-primary, button[type="button"].ds-btn-primary').trigger('click')
    await flushPromises()
    expect(mockUpdateAdminEvent).toHaveBeenCalledWith(1, expect.objectContaining({ ticket_layout: 'tabs' }))
    wrapper.unmount()
  })
})

describe('AdminEventFormView tabs', () => {
  it('shows only the form tabs for a new event and all tabs once it exists', async () => {
    const newWrapper = await mountAtNew()
    await flushPromises()
    expect(newWrapper.findAll('.event-tabs .ds-tab').map((b) => b.text())).toEqual(['Details', 'Media', 'Sales'])
    newWrapper.unmount()
    const wrapper = await mountAtEventId('1')
    await flushPromises()
    expect(wrapper.findAll('.event-tabs .ds-tab').map((b) => b.text())).toEqual(['Details', 'Media', 'Sales', 'Schedule', 'Tickets', 'Coupons', 'Volunteers'])
    wrapper.unmount()
  })

  it('shows one section at a time', async () => {
    const wrapper = await mountAtEventId('1')
    await flushPromises()
    expect(wrapper.findAll('h2').map((h) => h.text())).toEqual(['Repeats']) // the Repeats card sits under the details (wave 14 item 6)
    expect(wrapper.find('.ds-card').isVisible()).toBe(true)
    await wrapper.findAll('.event-tabs .ds-tab').find((b) => b.text() === 'Coupons')!.trigger('click')
    expect(wrapper.findAll('h2').map((h) => h.text())).toEqual(['Coupons'])
    expect(wrapper.find('.event-tab-pane').attributes('style')).toContain('display: none')
    wrapper.unmount()
  })
})

describe('AdminEventFormView slug auto-fill', () => {
  it('auto-fills the slug from the title for a new event, until the slug is manually edited', async () => {
    const wrapper = await mountAtNew()
    const titleInput = wrapper.findAll('input')[0]
    const slugInput = wrapper.findAll('input')[2]

    await titleInput.setValue('Durga Puja 2026!')
    expect((slugInput.element as HTMLInputElement).value).toBe('durga-puja-2026')

    await slugInput.setValue('custom-slug')
    await titleInput.setValue('Something Else Entirely')

    expect((slugInput.element as HTMLInputElement).value).toBe('custom-slug')

    wrapper.unmount()
  })

  it('does not auto-fill the slug when editing an existing event', async () => {
    const wrapper = await mountAtEventId('1')
    await flushPromises()

    const titleInput = wrapper.findAll('input')[0]
    const slugInput = wrapper.findAll('input')[2]

    await titleInput.setValue('Durga Puja Renamed')

    expect((slugInput.element as HTMLInputElement).value).toBe('durga-puja')

    wrapper.unmount()
  })
})

describe('AdminEventFormView past-event notice', () => {
  it('shows a past-event notice when editing an event whose start date is in the past', async () => {
    mockFetchAdminEvent.mockResolvedValue({
      id: 1, title: 'Durga Puja 2020', slug: 'durga-puja-2020', event_type: 'festival',
      short_description: null, description: null,
      start_datetime: '2020-10-01T10:00:00Z', end_datetime: null,
      venue: null, address: null, capacity: null, banner_image: null, published: true,
      sessions: [], task_assignments: [],
    })

    const wrapper = await mountAtEventId('1')
    await flushPromises()

    expect(wrapper.text()).toContain('This event has already happened')
    wrapper.unmount()
  })

  it('does not show a past-event notice for an upcoming event', async () => {
    const wrapper = await mountAtEventId('1')
    await flushPromises()

    expect(wrapper.text()).not.toContain('This event has already happened')
    wrapper.unmount()
  })

  it('does not show a past-event notice for a new event', async () => {
    const wrapper = await mountAtNew()
    await flushPromises()

    expect(wrapper.text()).not.toContain('This event has already happened')
    wrapper.unmount()
  })
})

describe('AdminEventFormView attribution', () => {
  it('shows who created and last edited the event when editing', async () => {
    mockFetchAdminEvent.mockResolvedValue({
      id: 1,
      title: 'Durga Puja',
      slug: 'durga-puja',
      event_type: 'festival',
      short_description: null,
      description: null,
      start_datetime: '2026-10-01T10:00:00Z',
      end_datetime: null,
      venue: null,
      address: null,
      capacity: null,
      banner_image: null,
      published: true,
      sessions: [],
      task_assignments: [],
      created_by_email: 'creator@example.com',
      updated_by_email: 'editor@example.com',
    })

    const wrapper = await mountAtEventId('1')
    await flushPromises()

    expect(wrapper.text()).toContain('Created by creator@example.com')
    expect(wrapper.text()).toContain('Last edited by editor@example.com')

    wrapper.unmount()
  })
})

describe('AdminEventFormView banner upload', () => {
  it('uploads a banner image and shows the preview', async () => {
    mockUploadEventBanner.mockResolvedValue({ banner_image: 'https://x/banner.jpg' })

    const wrapper = await mountAtEventId('1')
    await flushPromises()

    const file = new File(['data'], 'banner.jpg', { type: 'image/jpeg' })
    const fileInput = wrapper.find('input[type="file"][accept*="image/jpeg"]')
    Object.defineProperty(fileInput.element, 'files', { value: [file] })
    await fileInput.trigger('change')
    await flushPromises()

    expect(mockUploadEventBanner).toHaveBeenCalledWith(1, file)
    expect(wrapper.find('img[alt="Event banner"]').attributes('src')).toBe('https://x/banner.jpg')

    wrapper.unmount()
  })

  it('removes the banner image', async () => {
    // No ticket types in this test, so its own "Remove" button (the banner's) can't collide
    // with the ticket type table's "Remove" button.
    mockFetchAdminTicketTypes.mockResolvedValue({ items: [] })
    mockFetchAdminEvent.mockResolvedValue({
      id: 1,
      title: 'Durga Puja',
      slug: 'durga-puja',
      event_type: 'festival',
      short_description: null,
      description: null,
      start_datetime: '2026-10-01T10:00:00Z',
      end_datetime: null,
      venue: null,
      address: null,
      capacity: null,
      banner_image: 'https://x/banner.jpg',
      published: true,
      sessions: [],
      task_assignments: [],
      created_by_email: null,
      updated_by_email: null,
    })
    mockUpdateAdminEvent.mockResolvedValue({ banner_image: null })

    const wrapper = await mountAtEventId('1')
    await flushPromises()

    expect(wrapper.find('img[alt="Event banner"]').exists()).toBe(true)

    await wrapper.findAll('button').find((b) => b.text() === 'Remove')!.trigger('click')
    await flushPromises()

    expect(mockUpdateAdminEvent).toHaveBeenCalledWith(1, { banner_image: null })
    expect(wrapper.find('img[alt="Event banner"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('adds a banner to the slider without touching the legacy banner_image', async () => {
    mockAddEventBanner.mockResolvedValue({
      banners: [{ id: 1, image_url: 'https://x/slide-one.jpg', sort_order: 0 }],
    })

    const wrapper = await mountAtEventId('1')
    await flushPromises()

    const file = new File(['data'], 'slide-one.jpg', { type: 'image/jpeg' })
    const fileInputs = wrapper.findAll('input[type="file"][accept*="image/jpeg"]')
    Object.defineProperty(fileInputs[1].element, 'files', { value: [file] })
    await fileInputs[1].trigger('change')
    await flushPromises()

    expect(mockAddEventBanner).toHaveBeenCalledWith(1, file)
    expect(wrapper.find('img[alt="Event banner slide"]').attributes('src')).toBe('https://x/slide-one.jpg')

    wrapper.unmount()
  })

  it('removes a banner from the slider', async () => {
    mockFetchAdminEvent.mockResolvedValue({
      id: 1,
      title: 'Durga Puja',
      slug: 'durga-puja',
      event_type: 'festival',
      short_description: null,
      description: null,
      start_datetime: '2026-10-01T10:00:00Z',
      end_datetime: null,
      venue: null,
      address: null,
      capacity: null,
      banner_image: null,
      banners: [{ id: 1, image_url: 'https://x/slide-one.jpg', sort_order: 0 }],
      published: true,
      sessions: [],
      task_assignments: [],
    })
    mockDeleteEventBanner.mockResolvedValue({ banners: [] })

    const wrapper = await mountAtEventId('1')
    await flushPromises()

    expect(wrapper.find('img[alt="Event banner slide"]').exists()).toBe(true)

    await wrapper.find('button[aria-label="Remove this banner"]').trigger('click')
    await flushPromises()

    expect(mockDeleteEventBanner).toHaveBeenCalledWith(1, 1)
    expect(wrapper.find('img[alt="Event banner slide"]').exists()).toBe(false)

    wrapper.unmount()
  })
})

describe('AdminEventFormView description style', () => {
  async function saveWith(initialStyle: string | null, choice: string) {
    mockUpdateAdminEvent.mockResolvedValue({})
    mockFetchAdminEvent.mockResolvedValue({ ...(await mockFetchAdminEvent()), description_style: initialStyle })
    const wrapper = await mountAtEventId('1')
    await flushPromises()
    await chooseOption(wrapper, choice, wrapper.findAll('.base-select-button').findIndex((b) => b.attributes('aria-label') === 'Description style'))
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    wrapper.unmount()
  }

  it('sends the per-event description style override', async () => {
    await saveWith(null, 'source')
    expect(mockUpdateAdminEvent).toHaveBeenLastCalledWith(1, expect.objectContaining({ description_style: 'source' }))
  })

  it('sends null when an existing override is set back to "Site default"', async () => {
    await saveWith('cormorant', '')
    expect(mockUpdateAdminEvent).toHaveBeenLastCalledWith(1, expect.objectContaining({ description_style: null }))
  })
})

describe('AdminEventFormView ticket payment setting', () => {
  async function open(initial: string) {
    mockUpdateAdminEvent.mockResolvedValue({})
    mockFetchAdminEvent.mockResolvedValue({ ...(await mockFetchAdminEvent()), ticket_payment_methods: initial })
    const wrapper = await mountAtEventId('1')
    await flushPromises()
    return wrapper
  }
  const save = async (wrapper: Awaited<ReturnType<typeof open>>) => {
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
  }

  it('both ticked = "qr,app"; unticking Vipps-QR saves "app" only', async () => {
    const wrapper = await open('both')
    expect((wrapper.find('input[aria-label="Accept Vipps-QR"]').element as HTMLInputElement).checked).toBe(true)
    expect((wrapper.find('input[aria-label="Accept Vipps-App"]').element as HTMLInputElement).checked).toBe(true)

    await wrapper.find('input[aria-label="Accept Vipps-QR"]').setValue(false)
    await save(wrapper)

    expect(mockUpdateAdminEvent).toHaveBeenLastCalledWith(1, expect.objectContaining({ ticket_payment_methods: 'app' }))
    wrapper.unmount()
  })

  it('the last ticked method cannot be unticked', async () => {
    const wrapper = await open('qr')
    const qr = wrapper.find('input[aria-label="Accept Vipps-QR"]')
    await qr.setValue(false)
    expect((qr.element as HTMLInputElement).checked).toBe(true)
    await save(wrapper)
    expect(mockUpdateAdminEvent).toHaveBeenLastCalledWith(1, expect.objectContaining({ ticket_payment_methods: 'qr' }))

    wrapper.unmount()
  })

  it('ticking Vipps-App on a QR-only event saves "qr,app"', async () => {
    const wrapper = await open('qr')
    await wrapper.find('input[aria-label="Accept Vipps-App"]').setValue(true)
    await save(wrapper)
    expect(mockUpdateAdminEvent).toHaveBeenLastCalledWith(1, expect.objectContaining({ ticket_payment_methods: 'qr,app' }))
    wrapper.unmount()
  })

  it('Cash can be ticked next to the Vipps methods and saves its own wording', async () => {
    const wrapper = await open('qr,app')
    expect(wrapper.find('textarea[aria-label="Cash wording"]').exists()).toBe(false)

    await wrapper.find('input[aria-label="Accept Cash"]').setValue(true)
    await wrapper.find('textarea[aria-label="Cash wording"]').setValue('Not confirmed until you pay.')
    await save(wrapper)

    expect(mockUpdateAdminEvent).toHaveBeenLastCalledWith(
      1,
      expect.objectContaining({ ticket_payment_methods: 'qr,app,cash', cash_note: 'Not confirmed until you pay.' }),
    )
    wrapper.unmount()
  })
})

describe('AdminEventFormView — ticket sales cut-off', () => {
  const save = async (wrapper: Awaited<ReturnType<typeof mountAtEventId>>) => {
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
  }

  it('saves the "Ticket sales close at" time', async () => {
    mockUpdateAdminEvent.mockResolvedValue({})
    const wrapper = await mountAtEventId('1')
    await flushPromises()

    await wrapper.find('input[aria-label="Ticket sales close at"]').setValue('2026-10-09T18:00')
    await save(wrapper)

    expect(mockUpdateAdminEvent).toHaveBeenLastCalledWith(1, expect.objectContaining({ sales_close_at: expect.stringMatching(/^2026-10-09T/) }))
    wrapper.unmount()
  })

  it('loads an existing cut-off into the field and clears it when emptied', async () => {
    mockUpdateAdminEvent.mockResolvedValue({})
    mockFetchAdminEvent.mockResolvedValue({ ...(await mockFetchAdminEvent()), sales_close_at: '2026-10-09T16:00:00Z' })
    const wrapper = await mountAtEventId('1')
    await flushPromises()

    expect((wrapper.find('input[aria-label="Ticket sales close at"]').element as HTMLInputElement).value).not.toBe('')
    await wrapper.find('input[aria-label="Ticket sales close at"]').setValue('')
    await save(wrapper)

    expect(mockUpdateAdminEvent).toHaveBeenLastCalledWith(1, expect.objectContaining({ sales_close_at: null }))
    wrapper.unmount()
  })
})

describe('AdminEventFormView and the optional modules', () => {
  it('all on: the Coupons and Volunteer assignments sections are there', async () => {
    const wrapper = await mountAtEventId('1', 'Coupons')
    await flushPromises()
    expect(wrapper.findAll('h2').map((h) => h.text())).toContain('Coupons')
    expect(mockFetchAdminCoupons).toHaveBeenCalled()
    await wrapper.findAll('.event-tabs .ds-tab').find((b) => b.text() === 'Volunteers')!.trigger('click')
    expect(wrapper.findAll('h2').map((h) => h.text())).toContain('Volunteer assignments')
    wrapper.unmount()
  })

  it('Coupons and Volunteering off: neither section, no coupon request, no coupon boxes', async () => {
    off.keys = ['coupons', 'volunteering']
    const wrapper = await mountAtEventId('1')
    await flushPromises()
    const headings = wrapper.findAll('h2').map((h) => h.text())
    expect(headings).not.toContain('Coupons')
    expect(headings).not.toContain('Volunteer assignments')
    expect(mockFetchAdminCoupons).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('Coupon order: max adult tickets')
    wrapper.unmount()
  })

  it('Tickets off: no ticket types, sales times, capacity, ticket payment or ticket request', async () => {
    off.keys = ['tickets', 'coupons']
    const wrapper = await mountAtEventId('1')
    await flushPromises()
    expect(wrapper.findAll('h2').map((h) => h.text())).not.toContain('Ticket types')
    expect(mockFetchAdminTicketTypes).not.toHaveBeenCalled()
    const text = wrapper.text()
    for (const gone of ['Ticket sales open at', 'Ticket sales close at', 'Max tickets per email', 'Ticket payment', 'Capacity']) expect(text).not.toContain(gone)
    expect(text).toContain('Title')
    wrapper.unmount()
  })
})

