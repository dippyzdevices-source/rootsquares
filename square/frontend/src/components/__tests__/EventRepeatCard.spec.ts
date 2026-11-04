// Tests for EventRepeatCard (4 cases), e.g. EventRepeatCard; offers to make a one-off event repeat and sends the chosen rule; sends a monthly rule with the chosen weekday of the month and a number.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { chooseOption } from '../../test-utils/baseSelect'

const api = { fetchEventSeries: vi.fn(), repeatEvent: vi.fn(), updateFollowingEvents: vi.fn(), endEventSeries: vi.fn() }
vi.mock('../../services/eventSeriesApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/eventSeriesApi')>()),
  fetchEventSeries: (...a: unknown[]) => api.fetchEventSeries(...a),
  repeatEvent: (...a: unknown[]) => api.repeatEvent(...a),
  updateFollowingEvents: (...a: unknown[]) => api.updateFollowingEvents(...a),
  endEventSeries: (...a: unknown[]) => api.endEventSeries(...a),
}))

import EventRepeatCard from '../EventRepeatCard.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }
const future = (days: number) => new Date(Date.now() + days * 86400000).toISOString()
const series = {
  id: 1, frequency: 'weekly', interval_weeks: 1, nth: null, until_date: null, max_count: null, ended: false, label: 'Every week on Sunday',
  occurrences: [
    { id: 10, slug: 'a', title: 'A', start_datetime: future(7), status: 'scheduled', published: true, has_orders: true },
    { id: 11, slug: 'b', title: 'B', start_datetime: future(14), status: 'scheduled', published: true, has_orders: false },
    { id: 12, slug: 'c', title: 'C', start_datetime: future(21), status: 'cancelled', published: true, has_orders: true },
  ],
}
let wrapper: ReturnType<typeof mount> | null = null

beforeEach(() => vi.clearAllMocks())
afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
})

describe('EventRepeatCard', () => {
  it('offers to make a one-off event repeat and sends the chosen rule', async () => {
    api.fetchEventSeries.mockResolvedValue({ series: null })
    api.repeatEvent.mockResolvedValue({ series, created: 16 })
    wrapper = mount(EventRepeatCard, { props: { eventId: 5 }, global: { stubs }, attachTo: document.body })
    await flushPromises()
    expect(wrapper.text()).toContain('This event happens once')
    await wrapper.find('.make-repeat').trigger('click')
    await flushPromises()
    ;(document.body.querySelector('.repeat-interval') as HTMLInputElement).value = '2'
    document.body.querySelector('.repeat-interval')!.dispatchEvent(new Event('input'))
    ;(document.body.querySelector('.confirm-repeat') as HTMLElement).click()
    await flushPromises()
    expect(api.repeatEvent).toHaveBeenCalledWith(5, { frequency: 'weekly', interval_weeks: 2, until_date: null, max_count: null })
    expect(wrapper.text()).toContain('Every week on Sunday')
  })

  it('sends a monthly rule with the chosen weekday of the month and a number of times', async () => {
    api.fetchEventSeries.mockResolvedValue({ series: null })
    api.repeatEvent.mockResolvedValue({ series, created: 5 })
    wrapper = mount(EventRepeatCard, { props: { eventId: 5 }, global: { stubs }, attachTo: document.body })
    await flushPromises()
    await wrapper.find('.make-repeat').trigger('click')
    await flushPromises()
    const body = new (await import('@vue/test-utils')).DOMWrapper(document.body)
    await chooseOption(body, 'monthly_weekday', 0)
    await flushPromises()
    await chooseOption(body, '5', 1)
    await chooseOption(body, 'count', 2)
    await flushPromises()
    ;(document.body.querySelector('.repeat-count') as HTMLInputElement).value = '6'
    document.body.querySelector('.repeat-count')!.dispatchEvent(new Event('input'))
    ;(document.body.querySelector('.confirm-repeat') as HTMLElement).click()
    await flushPromises()
    expect(api.repeatEvent).toHaveBeenCalledWith(5, { frequency: 'monthly_weekday', nth: 5, until_date: null, max_count: 6 })
  })

  it('shows the series, copies the wording on request and stops it after confirmation', async () => {
    api.fetchEventSeries.mockResolvedValue({ series })
    api.updateFollowingEvents.mockResolvedValue({ updated: 3, skipped_with_orders: 1 })
    api.endEventSeries.mockResolvedValue({ removed: 2, cancelled: 1 })
    wrapper = mount(EventRepeatCard, { props: { eventId: 10 }, global: { stubs }, attachTo: document.body })
    await flushPromises()
    expect(wrapper.text()).toContain('Every week on Sunday')
    expect(wrapper.text()).toContain('2 coming up')
    expect(wrapper.text()).toContain('1 cancelled')
    expect(wrapper.text()).toContain('tickets sold')
    await wrapper.find('.update-following').trigger('click')
    await flushPromises()
    expect(api.updateFollowingEvents).toHaveBeenCalledWith(10)
    await wrapper.find('.end-series').trigger('click')
    await flushPromises()
    ;(document.body.querySelector('.confirm-end') as HTMLElement).click()
    await flushPromises()
    expect(api.endEventSeries).toHaveBeenCalledWith(10)
  })
})
