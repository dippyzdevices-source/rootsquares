// Tests for AdminTicketsView (8 cases), e.g. AdminTicketsView; lists tickets with customer, type, event, and status; shows checked-in details for a used ticket.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chooseOption } from '../../../test-utils/baseSelect'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminTickets = vi.fn()
const mockExportTickets = vi.fn()
const mockDownloadBlob = vi.fn()

vi.mock('../../../services/adminEventsApi', () => ({
  fetchAdminEvents: vi.fn().mockResolvedValue({
    items: [
      { id: 7, title: 'Durga Puja 2026' },
      { id: 9, title: 'Saraswati Puja 2027' },
    ],
  }),
}))

vi.mock('../../../services/adminTicketsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminTicketsApi')>(
    '../../../services/adminTicketsApi',
  )
  return {
    ...actual,
    fetchAdminTickets: (...args: unknown[]) => mockFetchAdminTickets(...args),
    exportTickets: (...args: unknown[]) => mockExportTickets(...args),
  }
})

vi.mock('../../../utils/download', () => ({
  downloadBlob: (...args: unknown[]) => mockDownloadBlob(...args),
}))

import AdminTicketsView from '../AdminTicketsView.vue'

const baseTicket = {
  id: 1,
  ticket_code: 'abc123',
  status: 'valid',
  customer_name: 'Priya Das',
  customer_email: 'priya@example.com',
  ticket_type: 'Adult',
  event_id: 1,
  event_title: 'Durga Puja 2026',
  checked_in_at: null,
  checked_in_by: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminTickets.mockResolvedValue({
    items: [baseTicket],
    page: 1,
    per_page: 20,
    total: 1,
    total_pages: 1,
  })
})

describe('AdminTicketsView', () => {
  it('lists tickets with customer, type, event, and status', async () => {
    const wrapper = mount(AdminTicketsView)
    await flushPromises()

    expect(wrapper.text()).toContain('abc123')
    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).toContain('Not checked in yet')
  })

  it('shows checked-in details for a used ticket', async () => {
    mockFetchAdminTickets.mockResolvedValue({
      items: [
        {
          ...baseTicket,
          status: 'used',
          checked_in_at: '2026-10-10T18:00:00+00:00',
          checked_in_by: 'door@example.com',
        },
      ],
      page: 1,
      per_page: 20,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(AdminTicketsView)
    await flushPromises()

    expect(wrapper.text()).toContain('door@example.com')
  })

  it('shows an empty state when there are no tickets', async () => {
    mockFetchAdminTickets.mockResolvedValue({
      items: [], page: 1, per_page: 20, total: 0, total_pages: 0,
    })

    const wrapper = mount(AdminTicketsView)
    await flushPromises()

    expect(wrapper.text()).toContain('No tickets yet.')
  })

  it('shows an error state when the fetch fails', async () => {
    mockFetchAdminTickets.mockRejectedValue(new Error('boom'))

    const wrapper = mount(AdminTicketsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Could not load tickets.')
  })

  it('exports tickets to Excel', async () => {
    const fakeBlob = new Blob(['data'])
    mockExportTickets.mockResolvedValue(fakeBlob)

    const wrapper = mount(AdminTicketsView)
    await flushPromises()

    await wrapper.find('button.export-tickets').trigger('click')
    await flushPromises()

    expect(mockExportTickets).toHaveBeenCalled()
    expect(mockDownloadBlob).toHaveBeenCalledWith(fakeBlob, 'tickets.xlsx')
  })

  it('reloads with a status filter', async () => {
    const wrapper = mount(AdminTicketsView)
    await flushPromises()
    mockFetchAdminTickets.mockClear()

    await chooseOption(wrapper, 'used', 1)
    await flushPromises()

    expect(mockFetchAdminTickets).toHaveBeenCalledWith(
      expect.objectContaining({ status: ['used'] }),
    )
  })

  it('filters by event, sending the event id', async () => {
    const wrapper = mount(AdminTicketsView)
    await flushPromises()
    mockFetchAdminTickets.mockClear()

    await chooseOption(wrapper, '7', 0)
    await flushPromises()

    expect(mockFetchAdminTickets).toHaveBeenCalledWith(expect.objectContaining({ eventId: ['7'], page: 1 }))
  })
})
