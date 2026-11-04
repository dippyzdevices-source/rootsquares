// An Event pass holds one event (W11, ADR 044): once it has one, the New event button gives way to a note.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminEvents = vi.fn()

vi.mock('../../../services/squareConfig', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../services/squareConfig')>()
  return { ...actual, squareProfile: { ...actual.squareProfile, eventPass: { phase: 'live', liveUntil: '', archiveUntil: '' } } }
})
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
})

describe('AdminEventsListView on an Event pass', () => {
  it('offers New event while the pass has no event', async () => {
    mockFetchAdminEvents.mockResolvedValue({ items: [], page: 1, per_page: 50, total: 0, total_pages: 1 })
    const wrapper = mount(AdminEventsListView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('New event')
    expect(wrapper.find('[data-testid="pass-one-event"]').exists()).toBe(false)
  })

  it('says the pass holds one event once it has one, and offers no New event', async () => {
    mockFetchAdminEvents.mockResolvedValue({
      items: [{ id: 1, title: 'Gala Night', event_type: 'festival', published: true, start_datetime: new Date().toISOString(), end_datetime: null }],
      page: 1,
      per_page: 50,
      total: 1,
      total_pages: 1,
    })
    const wrapper = mount(AdminEventsListView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('[data-testid="pass-one-event"]').text()).toContain('holds one event')
    expect(wrapper.text()).not.toContain('New event')
  })
})
