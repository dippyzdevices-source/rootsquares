// Tests for AdminEventsListView (4 cases), e.g. AdminEventsListView; shows each event as Draft, Live or Expired and offers the same pills a; filters the table by the chosen pill.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminEvents = vi.fn()

vi.mock('../../../services/adminEventsApi', () => ({
  fetchAdminEvents: (...args: unknown[]) => mockFetchAdminEvents(...args),
  deleteAdminEvent: vi.fn(),
  duplicateAdminEvent: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

import AdminEventsListView from '../AdminEventsListView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
  const now = Date.now()
  const iso = (days: number) => new Date(now + days * 86400000).toISOString()
  mockFetchAdminEvents.mockResolvedValue({
    items: [
      { id: 1, title: 'Upcoming Puja', event_type: 'festival', published: true, start_datetime: iso(30), end_datetime: null },
      { id: 2, title: 'Old Puja', event_type: 'festival', published: true, start_datetime: iso(-60), end_datetime: iso(-59) },
      { id: 3, title: 'Unpublished Fest', event_type: 'festival', published: false, start_datetime: iso(10), end_datetime: null },
    ],
    page: 1,
    per_page: 50,
    total: 3,
    total_pages: 1,
  })
})

describe('AdminEventsListView', () => {
  it('shows each event as Draft, Live or Expired and offers the same pills as filters', async () => {
    const wrapper = mount(AdminEventsListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.findAll('.ds-tag').map((t) => t.text())).toEqual(['All', 'Live', 'Draft', 'Expired'])
    expect(wrapper.findAll('.event-phase').map((p) => p.text()).sort()).toEqual(['Draft', 'Expired', 'Live'])
  })

  it('filters the table by the chosen pill', async () => {
    const wrapper = mount(AdminEventsListView, { global: { stubs } })
    await flushPromises()
    const tag = (label: string) => wrapper.findAll('.ds-tag').find((t) => t.text() === label)!

    await tag('Live').trigger('click')
    expect(wrapper.text()).toContain('Upcoming Puja')
    expect(wrapper.text()).not.toContain('Old Puja')

    await tag('Expired').trigger('click')
    expect(wrapper.text()).toContain('Old Puja')
    expect(wrapper.text()).not.toContain('Unpublished Fest')

    await tag('Draft').trigger('click')
    expect(wrapper.text()).toContain('Unpublished Fest')
    expect(wrapper.text()).not.toContain('Upcoming Puja')
  })

  it('searches by title, after the pills in the toolbar, and combines with the pill filter', async () => {
    const wrapper = mount(AdminEventsListView, { global: { stubs } })
    await flushPromises()

    const toolbar = wrapper.find('.ds-toolbar').element
    expect(toolbar.children[0].classList.contains('ds-toolbar-pills')).toBe(true)
    expect(toolbar.children[1].classList.contains('ds-toolbar-search')).toBe(true)

    await wrapper.find('input[type="search"]').setValue('puja')
    expect(wrapper.text()).toContain('Upcoming Puja')
    expect(wrapper.text()).toContain('Old Puja')
    expect(wrapper.text()).not.toContain('Unpublished Fest')

    await wrapper.findAll('.ds-tag').find((t) => t.text() === 'Expired')!.trigger('click')
    expect(wrapper.text()).toContain('Old Puja')
    expect(wrapper.text()).not.toContain('Upcoming Puja')
  })
})
