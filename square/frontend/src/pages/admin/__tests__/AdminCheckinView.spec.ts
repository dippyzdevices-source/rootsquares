// Tests for AdminCheckinView (6 cases), e.g. AdminCheckinView; links to the real scanner; requests the used-tickets list sorted by most recently checked in, not.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchCheckinSummary = vi.fn()
const mockFetchAdminTickets = vi.fn()

vi.mock('../../../services/checkinApi', () => ({
  fetchCheckinSummary: (...args: unknown[]) => mockFetchCheckinSummary(...args),
}))

vi.mock('../../../services/adminTicketsApi', () => ({
  fetchAdminTickets: (...args: unknown[]) => mockFetchAdminTickets(...args),
}))

import AdminCheckinView from '../AdminCheckinView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchCheckinSummary.mockResolvedValue({ total_tickets: 10, checked_in_count: 4 })
  mockFetchAdminTickets.mockResolvedValue({
    items: [],
    page: 1,
    per_page: 10,
    total: 0,
    total_pages: 0,
  })
})

describe('AdminCheckinView', () => {
  it('links to the real scanner', async () => {
    const wrapper = mount(AdminCheckinView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(wrapper.find('a[to="/checkin"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Open the scanner')
  })

  it('requests the used-tickets list sorted by most recently checked in, not created', async () => {
    mount(AdminCheckinView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(mockFetchAdminTickets).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'used', sort: 'checked_in_at_desc' }),
    )
  })

  it('shows real check-in stats derived from the global summary', async () => {
    const wrapper = mount(AdminCheckinView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Checked in')
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('Not yet checked in')
    expect(wrapper.text()).toContain('6')
    expect(wrapper.text()).toContain('Check-in rate')
    expect(wrapper.text()).toContain('40%')
  })

  it('shows an empty state when there are no scans yet', async () => {
    const wrapper = mount(AdminCheckinView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('No check-ins yet.')
  })

  it('lists recent scans with who, when, and the checked-in-by volunteer', async () => {
    mockFetchAdminTickets.mockResolvedValue({
      items: [
        {
          id: 1,
          ticket_code: 'abc123',
          status: 'used',
          customer_name: 'Priya Das',
          customer_email: 'priya@example.com',
          ticket_type: 'Adult',
          event_id: 1,
          event_title: 'Durga Puja 2026',
          checked_in_at: '2026-10-10T18:00:00+00:00',
          checked_in_by: 'door@example.com',
        },
      ],
      page: 1,
      per_page: 10,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(AdminCheckinView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).toContain('abc123')
    expect(wrapper.text()).toContain('door@example.com')
    expect(wrapper.text()).toContain('Checked in')
  })
})
