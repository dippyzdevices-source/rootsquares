// Tests for AdminAccountingDashboardView (24 cases), e.g. AdminAccountingDashboardView; shows one section at a time behind tabs, with counts; shows a pending sponsorship enquiry with its contact and requirements,.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

const mockFetchEventAccountingSummary = vi.fn()
const mockFetchEventCollections = vi.fn()
const mockExportEventBuyers = vi.fn()
const mockFetchEventExpenses = vi.fn()
const mockDeleteExpense = vi.fn()
const mockFetchEventContributions = vi.fn()
const mockDeleteContribution = vi.fn()
const mockUpdateContribution = vi.fn()
const mockDownloadEventReport = vi.fn()
const mockDownloadBlob = vi.fn()

vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: vi.fn().mockResolvedValue([
    { value: 'venue', label: 'Venue' },
    { value: 'food', label: 'Food' },
    { value: 'decoration', label: 'Decoration' },
  ]),
}))

vi.mock('../../../services/adminAccountingApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminAccountingApi')>(
    '../../../services/adminAccountingApi',
  )
  return {
    ...actual,
    fetchEventAccountingSummary: (...args: unknown[]) => mockFetchEventAccountingSummary(...args),
    fetchEventCollections: (...args: unknown[]) => mockFetchEventCollections(...args),
    fetchEventExpenses: (...args: unknown[]) => mockFetchEventExpenses(...args),
    deleteExpense: (...args: unknown[]) => mockDeleteExpense(...args),
    fetchEventContributions: (...args: unknown[]) => mockFetchEventContributions(...args),
    deleteContribution: (...args: unknown[]) => mockDeleteContribution(...args),
    updateContribution: (...args: unknown[]) => mockUpdateContribution(...args),
    downloadEventReport: (...args: unknown[]) => mockDownloadEventReport(...args),
    exportEventBuyers: (...args: unknown[]) => mockExportEventBuyers(...args),
  }
})

vi.mock('../../../services/adminTicketTypesApi', () => ({
  fetchAdminTicketTypes: vi.fn().mockResolvedValue({ items: [] }),
}))

vi.mock('../../../utils/download', () => ({ downloadBlob: (...args: unknown[]) => mockDownloadBlob(...args) }))

import AdminAccountingDashboardView from '../AdminAccountingDashboardView.vue'
import { toggleOption } from '../../../test-utils/baseSelect'

let currentWrapper: VueWrapper | null = null

const summary = {
  event: {
    id: 5,
    title: 'Durga Puja 2026',
    slug: 'durga-puja-2026',
    published: true,
    start_datetime: '2099-10-10T10:00:00',
    end_datetime: null,
  },
  collection_total: 350000,
  donations_total: 20000,
  sponsorships_total: 50000,
  expenses_total: 100000,
  recorded_expenses_total: 96860,
  processing_fees_total: 3140,
  fees_by_provider: [{ provider: 'vipps_app', convenience: 5000, processing: 3140 }],
  net_total: 250000,
  tickets_sold: 42,
  tickets_expected: 40,
  tickets_checked_in: 10,
  tickets_by_type: [{ name: 'Adult', count: 30 }, { name: 'Child', count: 12 }],
  tickets_by_sale_mode: [{ provider: 'manual', count: 38 }, { provider: 'vipps', count: 4 }],
  top_expense_categories: [
    { category: 'food', amount: 50000 },
    { category: 'venue', amount: 30000 },
    { category: 'decoration', amount: 20000 },
  ],
  coupon_usage: [
    {
      coupon_code: 'MEMBER',
      orders_count: 5,
      tickets_count: 12,
      discount_total: 6000,
      paid_total: 24000,
      gross_total: 30000,
      discount_percent: 20,
      is_active: false,
      max_redemptions: 40,
      by_ticket_type: [{ name: 'Adult', count: 8 }, { name: 'Child', count: 4 }],
    },
  ],
}

const collections = [
  {
    id: 1, date: '2026-10-01', order_number: 'ORD-1', customer_name: 'Anita Roy',
    customer_email: 'anita@example.com', tickets: ['2 × Adult'], payment_method: 'manual',
    amount: 200000, payment_status: 'paid',
  },
]

const expenses = [
  {
    id: 1, event_id: 5, date: '2026-09-20', description: 'Hall rental', category: 'venue',
    amount: 75000, vendor: 'Oslo Hall', notes: 'Paid via bank transfer', receipt_key: 'receipts/5/1-abc.png',
    receipt_url: 'https://example.com/receipt.png', created_by: null, created_at: '', updated_at: '',
  },
  {
    id: 2, event_id: 5, date: '2026-09-22', description: 'Flowers', category: 'decoration',
    amount: 25000, vendor: null, notes: null, receipt_key: null, receipt_url: null,
    created_by: null, created_at: '', updated_at: '',
  },
]

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/admin/accounting/:eventId', component: AdminAccountingDashboardView }],
  })
  router.push('/admin/accounting/5')
  await router.isReady()
  const wrapper = mount(AdminAccountingDashboardView, {
    global: { plugins: [router], stubs: { RouterLink: true } },
  })
  currentWrapper = wrapper
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchEventAccountingSummary.mockResolvedValue(summary)
  mockFetchEventCollections.mockResolvedValue({ items: collections })
  mockExportEventBuyers.mockResolvedValue(new Blob(['xlsx']))
  mockFetchEventExpenses.mockResolvedValue({ items: expenses, page: 1, per_page: 50, total: 2, total_pages: 1 })
  mockFetchEventContributions.mockResolvedValue({
    items: [
      { id: 1, event_id: 5, kind: 'donation', name: 'Maya Sen', email: null, amount: 20000, date: '2026-10-01', payment_method: 'cash', notes: null, status: 'paid', created_by: null, created_at: '2026-10-01T10:00:00' },
      { id: 2, event_id: 5, kind: 'sponsorship', name: 'Acme AS', email: null, amount: 50000, date: '2026-10-02', payment_method: null, notes: null, status: 'paid', created_by: null, created_at: '2026-10-02T10:00:00' },
      { id: 3, event_id: 5, kind: 'sponsorship', name: 'Fjord AS', contact_name: 'Kari', email: 'kari@fjord.no', phone: null, website: null, requirements: 'Banner at the entrance', amount: 120000, date: '2026-10-03', payment_method: null, notes: null, status: 'pending', created_by: null, created_at: '2026-10-03T10:00:00' },
    ],
    total: 3,
  })
  mockDeleteContribution.mockResolvedValue(undefined)
  mockUpdateContribution.mockResolvedValue({})
})

afterEach(() => {
  currentWrapper?.unmount()
  currentWrapper = null
})

describe('AdminAccountingDashboardView', () => {
  it('shows one section at a time behind tabs, with counts', async () => {
    const wrapper = await mountView()
    const visible = (title: string) => {
      const heading = wrapper.findAll('h2').find((h) => h.text().startsWith(title))
      return heading ? (heading.element.closest('section, .acc-pane') as HTMLElement).style.display !== 'none' : false
    }

    expect(wrapper.findAll('[role=tab]').map((b) => b.attributes('data-tab'))).toEqual(['overview', 'collections', 'expenses', 'donations'])
    expect(wrapper.find('[data-tab=donations]').text()).toContain('3')
    expect(visible('Collections')).toBe(false)
    expect(visible('Expenses')).toBe(false)

    await wrapper.find('[data-tab=collections]').trigger('click')
    expect(wrapper.find('[data-tab=collections]').attributes('aria-selected')).toBe('true')
    expect(visible('Collections')).toBe(true)
    expect(visible('Expenses')).toBe(false)

    await wrapper.find('[data-tab=donations]').trigger('click')
    expect(visible('Donations')).toBe(true)
    expect(visible('Collections')).toBe(false)
  })

  it('shows a pending sponsorship enquiry with its contact and requirements, and marks it received in one tap', async () => {
    const wrapper = await mountView()

    expect(wrapper.find('.contribution-contact').text()).toContain('Kari')
    expect(wrapper.find('.contribution-requirements').text()).toContain('Banner at the entrance')
    expect(wrapper.findAll('.mark-received')).toHaveLength(1)

    await wrapper.find('.mark-received').trigger('click')
    await flushPromises()
    expect(mockUpdateContribution).toHaveBeenCalledWith(3, { status: 'paid' })
  })

  it('shows donation and sponsorship cards and lists them, and deleting reloads', async () => {
    const wrapper = await mountView()

    expect(wrapper.find('.donations-card').text()).toContain('200 kr')
    expect(wrapper.find('.sponsorships-card').text()).toContain('500 kr')
    expect(wrapper.text()).toContain('Maya Sen')
    expect(wrapper.text()).toContain('Acme AS')

    await wrapper.find('button[aria-label="Delete Maya Sen"]').trigger('click')
    const body = new DOMWrapper(document.body)
    const confirm = body.findAll('button').find((b) => b.text() === 'Delete')
    await confirm!.trigger('click')
    await flushPromises()

    expect(mockDeleteContribution).toHaveBeenCalledWith(1)
    expect(mockFetchEventContributions).toHaveBeenCalledTimes(2)
  })

  it('shows the summary stats, collections, and expenses for the event', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).toContain('42') // tickets sold
    expect(wrapper.text()).toContain('Anita Roy')
    expect(wrapper.text()).toContain('Hall rental')
    expect(wrapper.text()).toContain('Flowers')
  })

  it('shows a provider commissions line and the processing fees as a read-only expense line', async () => {
    mockFetchEventExpenses.mockResolvedValue({
      items: expenses, page: 1, per_page: 50, total: 2, total_pages: 1,
      processing_fee_lines: [{ provider: 'vipps_app', amount: 3140 }],
    })
    const wrapper = await mountView()

    const note = wrapper.find('.provider-commissions')
    expect(note.text()).toContain('Provider commissions')
    expect(note.text()).toContain('31.40')
    const line = wrapper.find('tr.processing-fee-line')
    expect(line.exists()).toBe(true)
    expect(line.text()).toContain('processing fees')
    expect(line.findAll('button')).toHaveLength(0)
  })

  it('links the order number of each collection to its order detail page', async () => {
    const wrapper = await mountView()

    const targets = wrapper.findAll('router-link-stub').map((l) => l.attributes('to'))
    expect(targets).toContain('/admin/orders/1')
  })

  it('filters the collections and hands the same filter to the Excel export', async () => {
    const wrapper = await mountView()

    const search = wrapper.find('.ds-toolbar input[type="search"]')
    await search.setValue('anita')
    await search.trigger('keyup', { key: 'Enter' })
    await flushPromises()

    expect(mockFetchEventCollections).toHaveBeenLastCalledWith(5, expect.objectContaining({ q: 'anita' }))

    await wrapper.find('button.export-buyers').trigger('click')
    await flushPromises()
    expect(mockExportEventBuyers).toHaveBeenCalledWith(5, expect.objectContaining({ q: 'anita' }))
  })

  it('lets the payment-method filter take several values and hands them to the list and the export', async () => {
    const wrapper = await mountView()
    const toolbar = new DOMWrapper(wrapper.find('.ds-toolbar').element as HTMLElement)

    await toggleOption(toolbar, 'cash')
    await toggleOption(toolbar, 'vipps_qr')
    await flushPromises()

    expect(mockFetchEventCollections).toHaveBeenLastCalledWith(5, expect.objectContaining({ paymentMethods: ['cash', 'vipps_qr'] }))
    await wrapper.find('button.export-buyers').trigger('click')
    await flushPromises()
    expect(mockExportEventBuyers).toHaveBeenCalledWith(5, expect.objectContaining({ paymentMethods: ['cash', 'vipps_qr'] }))
  })

  it('says nothing matches, and keeps the filters, when a filter finds no collections', async () => {
    const wrapper = await mountView()
    mockFetchEventCollections.mockResolvedValue({ items: [] })

    const search = wrapper.find('.ds-toolbar input[type="search"]')
    await search.setValue('nobody')
    await search.trigger('keyup', { key: 'Enter' })
    await flushPromises()

    expect(wrapper.text()).toContain('No collections match this filter or search')
    expect(wrapper.find('.ds-toolbar input[type="search"]').exists()).toBe(true)
  })

  it('shows tickets by sale mode and top expense categories alongside tickets by type', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Tickets by type')
    expect(wrapper.text()).toContain('Tickets by Channels')
    expect(wrapper.text()).toContain('Manual')
    expect(wrapper.text()).toContain('Vipps')
    expect(wrapper.text()).toContain('Top Expenses')
    expect(wrapper.text()).toContain('Food')
    expect(wrapper.text()).toContain('500.00 kr')
  })

  it('shows coupon usage broken down by ticket type', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Coupon usage')
    expect(wrapper.text()).toContain('MEMBER')
    const row = wrapper.find('.coupon-usage tbody tr')
    const cells = row.findAll('td').map((c) => c.text())
    expect(cells[0]).toContain('20% off')
    expect(cells[0]).toContain('Retired')
    expect(cells[1]).toBe('5')
    expect(cells[2]).toContain('12')
    expect(cells[2]).toContain('/ 40')
    expect(cells).toHaveLength(6)
    expect(cells[3]).toBe('300.00 kr')
    expect(cells[4]).toContain('60.00 kr')
    expect(cells[5]).toBe('240.00 kr')
    const types = wrapper.findAll('.coupon-usage .coupon-types li').map((li) => li.findAll('span').map((x) => x.text()))
    expect(types).toEqual([['Adult', '8'], ['Child', '4']])
  })

  it('shows the event check-in rate', async () => {
    const wrapper = await mountView()

    const card = wrapper.find('.checkin-card')
    expect(card.text()).toContain('25%')
    expect(card.text()).toContain('10 of 40 tickets')
  })

  it('downloads the whole page as a PDF report named after the event', async () => {
    const blob = new Blob(['%PDF-'])
    mockDownloadEventReport.mockResolvedValue(blob)
    const wrapper = await mountView()

    await wrapper.find('.download-report').trigger('click')
    await flushPromises()

    expect(mockDownloadEventReport).toHaveBeenCalledWith(5, { details: false })
    expect(mockDownloadBlob).toHaveBeenCalledWith(blob, 'durga-puja-2026-accounting-report.pdf')
  })

  it('hides what each order bought until "Show details" is ticked, and the PDF report follows it', async () => {
    mockDownloadEventReport.mockResolvedValue(new Blob(['%PDF-']))
    const wrapper = await mountView()
    expect(wrapper.text()).not.toContain('2 × Adult')

    await wrapper.find('.ds-toolbar input[type="checkbox"]').setValue(true)
    expect(wrapper.text()).toContain('2 × Adult')

    await wrapper.find('.download-report').trigger('click')
    await flushPromises()
    expect(mockDownloadEventReport).toHaveBeenCalledWith(5, { details: true })
  })

  it('shows a free coupon order as "Coupon" with the code underneath', async () => {
    mockFetchEventCollections.mockResolvedValue({
      items: [{ ...collections[0], payment_method: null, coupon_code: 'BCAMEMBER26', amount: 0 }],
    })
    const wrapper = await mountView()

    const cell = wrapper.findAll('tbody tr td').find((td) => td.text().startsWith('Coupon'))
    expect(cell?.find('.ds-caption').text()).toBe('BCAMEMBER26')
  })

  it('opens the expense modal for editing an existing expense', async () => {
    const wrapper = await mountView()

    await wrapper.find('button[aria-label="Edit Hall rental"]').trigger('click')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    expect(body.text()).toContain('Edit expense')
  })

  it('deletes an expense after confirmation', async () => {
    mockDeleteExpense.mockResolvedValue(undefined)
    const wrapper = await mountView()

    await wrapper.find('button[aria-label="Delete Flowers"]').trigger('click')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    const confirmButton = body.findAll('button').find((b) => b.text() === 'Delete')
    await confirmButton!.trigger('click')
    await flushPromises()

    expect(mockDeleteExpense).toHaveBeenCalledWith(2)
  })

  it('opens the receipt viewer modal when the receipt button is clicked', async () => {
    const wrapper = await mountView()

    const receiptButton = wrapper.find('button[aria-label="View receipt for Hall rental"]')
    expect(receiptButton.exists()).toBe(true)
    expect(wrapper.find('button[aria-label="View receipt for Flowers"]').exists()).toBe(false)

    await receiptButton.trigger('click')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    expect(body.find('img[src="https://example.com/receipt.png"]').exists()).toBe(true)
  })

  it('shows expense notes in a read-only view modal without needing to edit', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).not.toContain('Paid via bank transfer')

    await wrapper.find('button[aria-label="View Hall rental"]').trigger('click')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    expect(body.text()).toContain('Expense details')
    expect(body.text()).toContain('Paid via bank transfer')
  })

  it('switches from the view modal to the edit form via its Edit button', async () => {
    const wrapper = await mountView()

    await wrapper.find('button[aria-label="View Hall rental"]').trigger('click')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    const editButton = body.findAll('button').find((b) => b.text() === 'Edit')
    await editButton!.trigger('click')
    await flushPromises()

    expect(body.text()).not.toContain('Expense details')
    expect(body.text()).toContain('Edit expense')
  })

  it('marks the event as Live (and not draft) when it is published and not over', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.event-phase').text()).toBe('Live')
    expect(wrapper.find('.acc-head-draft').exists()).toBe(false)
  })

  it('marks an unpublished event as Draft, with the draft watermark class on the header', async () => {
    mockFetchEventAccountingSummary.mockResolvedValue({ ...summary, event: { ...summary.event, published: false } })
    const wrapper = await mountView()
    expect(wrapper.find('.event-phase').text()).toBe('Draft')
    expect(wrapper.find('.acc-head-draft').exists()).toBe(true)
  })

  it('pages the collections and the expenses at 20 rows, each with its own pager', async () => {
    const manyCollections = Array.from({ length: 45 }, (_, i) => ({
      ...collections[0], id: i + 1, order_number: `ORD-${i + 1}`, customer_name: `Buyer ${i + 1}`,
    }))
    const manyExpenses = Array.from({ length: 25 }, (_, i) => ({
      ...expenses[1], id: i + 1, description: `Expense ${i + 1}`,
    }))
    mockFetchEventCollections.mockResolvedValue({ items: manyCollections })
    mockFetchEventExpenses.mockResolvedValue({ items: manyExpenses, total: 0 })
    const wrapper = await mountView()

    const bars = wrapper.findAll('nav[aria-label="Pagination"]')
    expect(bars).toHaveLength(2)
    expect(wrapper.text()).toContain('Buyer 20')
    expect(wrapper.text()).not.toContain('Buyer 21')
    expect(wrapper.text()).toContain('Expense 20')
    expect(wrapper.text()).not.toContain('Expense 21')
    expect(bars[0].text()).toContain('Page 1 of 3')
    expect(bars[1].text()).toContain('Page 1 of 2')

    await bars[0].findAll('button').find((b) => b.text() === 'Next')!.trigger('click')
    expect(wrapper.text()).toContain('Buyer 21')
    expect(wrapper.text()).not.toContain('Buyer 20')
    // the expenses pager is independent
    expect(wrapper.text()).toContain('Expense 20')
  })
})
