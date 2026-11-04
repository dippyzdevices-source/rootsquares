// The wrap-up page, the message to ticket buyers and the one-event note of an Event pass (W11, ADR 044).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchEventPass = vi.fn()
const mockDownload = vi.fn()
const mockCount = vi.fn()
const mockSend = vi.fn()
const mockDownloadBlob = vi.fn()
const mockFetchAdminEvents = vi.fn()

vi.mock('../../../services/adminEventPassApi', () => {
  class MessageInvalidError extends Error {
    errors: Record<string, string> = {}
  }
  class MessageRefusedError extends Error {
    code = ''
  }
  return {
    fetchEventPass: (...a: unknown[]) => mockFetchEventPass(...a),
    downloadEventExport: (...a: unknown[]) => mockDownload(...a),
    countBuyers: (...a: unknown[]) => mockCount(...a),
    messageBuyers: (...a: unknown[]) => mockSend(...a),
    MessageInvalidError,
    MessageRefusedError,
  }
})
vi.mock('../../../utils/download', () => ({ downloadBlob: (...a: unknown[]) => mockDownloadBlob(...a) }))
vi.mock('../../../services/adminEventsApi', () => ({ fetchAdminEvents: (...a: unknown[]) => mockFetchAdminEvents(...a) }))

import AdminEventPassView from '../AdminEventPassView.vue'
import AdminMessageBuyersView from '../AdminMessageBuyersView.vue'

const stubs = { RouterLink: true }

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchEventPass.mockResolvedValue({
    phase: 'archive',
    live_until: '2026-11-01T00:00:00Z',
    archive_until: '2026-12-16T00:00:00Z',
    events: [{ id: 1, title: 'Gala Night', slug: 'gala-night' }],
    export: ['Accounting report of each event (PDF)', 'All orders (Excel)'],
  })
  mockFetchAdminEvents.mockResolvedValue({ items: [{ id: 1, title: 'Gala Night' }], page: 1, per_page: 50, total: 1, total_pages: 1 })
})

describe('AdminEventPassView', () => {
  it('says the event is over, lists what the zip holds and downloads it', async () => {
    mockDownload.mockResolvedValue(new Blob(['zip']))
    const wrapper = mount(AdminEventPassView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('read-only archive')
    expect(wrapper.text()).toContain('deleted after')
    expect(wrapper.text()).toContain('Accounting report of each event (PDF)')
    await wrapper.find('button.download-export').trigger('click')
    await flushPromises()
    expect(mockDownload).toHaveBeenCalledTimes(1)
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'event-export.zip')
  })

  it('explains the live phase before the event is over', async () => {
    mockFetchEventPass.mockResolvedValue({ phase: 'live', live_until: '2026-11-01T00:00:00Z', archive_until: '2026-12-16T00:00:00Z', events: [], export: [] })
    const wrapper = mount(AdminEventPassView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Your Event pass is live')
    expect(wrapper.find('[data-testid="event-pass-dates"]').text()).toContain('read-only archive')
  })

  it('shows an error state when the summary cannot be loaded', async () => {
    mockFetchEventPass.mockRejectedValue(new Error('403'))
    const wrapper = mount(AdminEventPassView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain("Couldn't load the wrap-up")
  })
})

describe('AdminMessageBuyersView', () => {
  it('chooses the only event, shows who it reaches and sends the message', async () => {
    mockCount.mockResolvedValue({ count: 2, max: 250 })
    mockSend.mockResolvedValue({ sent: 2, failed: 0 })
    const wrapper = mount(AdminMessageBuyersView, { global: { stubs } })
    await flushPromises()
    expect(mockCount).toHaveBeenCalledWith(1) // one event: chosen for you
    expect(wrapper.find('[data-testid="buyers-count"]').text()).toContain('2 people')
    await wrapper.find('input[type="text"]').setValue('Doors open at 7')
    await wrapper.find('textarea').setValue('See you there')
    await wrapper.find('button.send-message').trigger('click')
    await flushPromises()
    expect(mockSend).toHaveBeenCalledWith({ event_id: 1, subject: 'Doors open at 7', message: 'See you there' })
  })

  it('cannot send while nobody has bought a ticket', async () => {
    mockCount.mockResolvedValue({ count: 0, max: 250 })
    const wrapper = mount(AdminMessageBuyersView, { global: { stubs } })
    await flushPromises()
    await wrapper.find('input[type="text"]').setValue('Hello')
    await wrapper.find('textarea').setValue('Hi')
    expect(wrapper.find('[data-testid="buyers-count"]').text()).toContain('Nobody has bought')
    expect(wrapper.find('button.send-message').attributes('disabled')).toBeDefined()
  })
})
