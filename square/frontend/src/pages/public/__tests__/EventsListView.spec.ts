// Tests for EventsListView (5 cases), e.g. EventsListView; does not show a Draft badge for a published event; shows a Draft badge when an admin\.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchEvents = vi.fn()

vi.mock('../../../services/eventsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/eventsApi')>(
    '../../../services/eventsApi',
  )
  return { ...actual, fetchEvents: (...args: unknown[]) => mockFetchEvents(...args) }
})

import EventsListView from '../EventsListView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

const baseEvent = {
  id: 1,
  title: 'Durga Puja 2026',
  slug: 'durga-puja-2026',
  short_description: null,
  event_type: 'festival',
  start_datetime: '2026-10-10T00:00:00Z',
  end_datetime: null,
  venue: null,
  banner_image: null,
  published: true,
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('EventsListView', () => {
  it('does not show a Draft badge for a published event', async () => {
    mockFetchEvents.mockResolvedValue({ items: [baseEvent], page: 1, per_page: 6, total: 1, total_pages: 1 })

    const wrapper = mount(EventsListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).not.toContain('Draft')
  })

  it('shows a Draft badge when an admin\'s request includes an unpublished event', async () => {
    mockFetchEvents.mockResolvedValue({
      items: [{ ...baseEvent, id: 2, title: 'Saraswati Puja 2027', slug: 'saraswati-puja-2027', published: false }],
      page: 1,
      per_page: 6,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(EventsListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Saraswati Puja 2027')
    expect(wrapper.text()).toContain('Draft')
  })

  it('puts the DRAFT watermark class on a draft card and on no published card', async () => {
    mockFetchEvents.mockResolvedValue({
      items: [baseEvent, { ...baseEvent, id: 2, title: 'Saraswati Puja 2027', slug: 'saraswati-puja-2027', published: false }],
      page: 1, per_page: 6, total: 2, total_pages: 1,
    })

    const wrapper = mount(EventsListView, { global: { stubs: {} } })
    await flushPromises()

    const cards = wrapper.findAll('.ds-event-card')
    expect(cards).toHaveLength(2)
    expect(cards[0].classes()).not.toContain('ds-event-card-draft')
    expect(cards[1].classes()).toContain('ds-event-card-draft')
  })

  it('shows a Sales closed pill on a card whose ticket sales have closed (the event stays listed)', async () => {
    mockFetchEvents.mockResolvedValue({
      items: [baseEvent, { ...baseEvent, id: 2, title: 'Saraswati Puja 2027', slug: 'saraswati-puja-2027', sales_closed: true }],
      page: 1, per_page: 6, total: 2, total_pages: 1,
    })
    const wrapper = mount(EventsListView, { global: { stubs: {} } })
    await flushPromises()

    const cards = wrapper.findAll('.ds-event-card')
    expect(cards).toHaveLength(2)
    expect(cards[0].find('.sales-closed-pill').exists()).toBe(false)
    expect(cards[1].find('.sales-closed-pill').text()).toBe('Sales closed')
  })
})
