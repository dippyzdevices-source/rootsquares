// Tests for AdminAccountingEventsView (8 cases), e.g. AdminAccountingEventsView; lists events as links into their accounting dashboard; shows an empty state when there are no events.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminEvents = vi.fn()

vi.mock('../../../services/adminEventsApi', () => ({
  fetchAdminEvents: (...args: unknown[]) => mockFetchAdminEvents(...args),
}))

import AdminAccountingEventsView from '../AdminAccountingEventsView.vue'

const stubs = { RouterLink: { template: '<a :to="to"><slot /></a>', props: ['to'] } }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AdminAccountingEventsView', () => {
  it('lists events as links into their accounting dashboard', async () => {
    mockFetchAdminEvents.mockResolvedValue({
      items: [{ id: 7, title: 'Durga Puja 2026', start_datetime: '2026-10-10T10:00:00Z' }],
      page: 1,
      per_page: 100,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(AdminAccountingEventsView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.find('a[to="/admin/accounting/7"]').exists()).toBe(true)
  })

  it('shows an empty state when there are no events', async () => {
    mockFetchAdminEvents.mockResolvedValue({ items: [], page: 1, per_page: 100, total: 0, total_pages: 0 })

    const wrapper = mount(AdminAccountingEventsView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('No events yet')
  })

  it('shows an error state when the fetch fails', async () => {
    mockFetchAdminEvents.mockRejectedValue(new Error('network error'))

    const wrapper = mount(AdminAccountingEventsView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load events")
  })

  it('groups events under year headings, most recent year first', async () => {
    mockFetchAdminEvents.mockResolvedValue({
      items: [
        { id: 1, title: 'Saraswati Puja 2027', start_datetime: '2027-01-15T10:00:00Z' },
        { id: 2, title: 'Durga Puja 2026', start_datetime: '2026-10-10T10:00:00Z' },
        { id: 3, title: 'Mahalaya 2026', start_datetime: '2026-09-01T10:00:00Z' },
      ],
      page: 1, per_page: 100, total: 3, total_pages: 1,
    })

    const wrapper = mount(AdminAccountingEventsView, { global: { stubs } })
    await flushPromises()

    const headings = wrapper.findAll('h2').map((h) => h.text())
    expect(headings).toEqual(['2027', '2026'])

    const yearIndex = wrapper.text().indexOf('2027')
    const durgaIndex = wrapper.text().indexOf('Durga Puja 2026')
    expect(yearIndex).toBeLessThan(durgaIndex)
  })

  it('filters events by a search term', async () => {
    mockFetchAdminEvents.mockResolvedValue({
      items: [
        { id: 1, title: 'Durga Puja 2026', start_datetime: '2026-10-10T10:00:00Z' },
        { id: 2, title: 'Saraswati Puja 2027', start_datetime: '2027-01-15T10:00:00Z' },
      ],
      page: 1, per_page: 100, total: 2, total_pages: 1,
    })

    const wrapper = mount(AdminAccountingEventsView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('input[type="search"]').setValue('saraswati')
    await flushPromises()

    expect(wrapper.text()).toContain('Saraswati Puja 2027')
    expect(wrapper.text()).not.toContain('Durga Puja 2026')
  })

  it('shows a "no matching events" state when the search has no results', async () => {
    mockFetchAdminEvents.mockResolvedValue({
      items: [{ id: 1, title: 'Durga Puja 2026', start_datetime: '2026-10-10T10:00:00Z' }],
      page: 1, per_page: 100, total: 1, total_pages: 1,
    })

    const wrapper = mount(AdminAccountingEventsView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('input[type="search"]').setValue('nothing matches this')
    await flushPromises()

    expect(wrapper.text()).toContain('No matching events')
  })

  it('shows a Draft / Live / Expired pill on each card and filters by it, with the pills before the search', async () => {
    const now = Date.now()
    const iso = (days: number) => new Date(now + days * 86400000).toISOString()
    mockFetchAdminEvents.mockResolvedValue({
      items: [
        { id: 1, title: 'Upcoming Puja', published: true, start_datetime: iso(30), end_datetime: null },
        { id: 2, title: 'Old Puja', published: true, start_datetime: iso(-60), end_datetime: iso(-59) },
        { id: 3, title: 'Unpublished Fest', published: false, start_datetime: iso(10), end_datetime: null },
      ],
      page: 1,
      per_page: 100,
      total: 3,
      total_pages: 1,
    })

    const wrapper = mount(AdminAccountingEventsView, { global: { stubs } })
    await flushPromises()

    const pills = wrapper.findAll('.event-phase').map((p) => p.text())
    expect(pills.sort()).toEqual(['Draft', 'Expired', 'Live'])
    // Only the draft card carries the dashed/watermark treatment.
    const draftCards = wrapper.findAll('.event-card-draft')
    expect(draftCards).toHaveLength(1)
    expect(draftCards[0].text()).toContain('Unpublished Fest')

    const toolbar = wrapper.find('.ds-toolbar').element
    expect(toolbar.children[0].classList.contains('ds-toolbar-pills')).toBe(true)
    expect(toolbar.children[1].classList.contains('ds-toolbar-search')).toBe(true)

    const tag = (label: string) => wrapper.findAll('.ds-toolbar-pills .ds-tag').find((b) => b.text() === label)!
    await tag('Live').trigger('click')
    expect(wrapper.text()).toContain('Upcoming Puja')
    expect(wrapper.text()).not.toContain('Old Puja')
    expect(wrapper.text()).not.toContain('Unpublished Fest')

    await tag('Draft').trigger('click')
    expect(wrapper.text()).toContain('Unpublished Fest')
    expect(wrapper.text()).not.toContain('Upcoming Puja')

    await tag('Expired').trigger('click')
    expect(wrapper.text()).toContain('Old Puja')
    expect(wrapper.text()).not.toContain('Unpublished Fest')
  })
})
