// Tests for AdminAuditLogView (10 cases), e.g. AdminAuditLogView; lists entries with actor, human-readable action label, and description; shows an empty state when there are no entries.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chooseOption } from '../../../test-utils/baseSelect'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAuditLog = vi.fn()
const mockExportAuditLog = vi.fn()
const mockDownloadBlob = vi.fn()

vi.mock('../../../services/adminAuditApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminAuditApi')>(
    '../../../services/adminAuditApi',
  )
  return {
    ...actual,
    fetchAuditLog: (...args: unknown[]) => mockFetchAuditLog(...args),
    exportAuditLog: (...args: unknown[]) => mockExportAuditLog(...args),
  }
})

vi.mock('../../../utils/download', () => ({ downloadBlob: (...args: unknown[]) => mockDownloadBlob(...args) }))

import AdminAuditLogView from '../AdminAuditLogView.vue'

const baseEntry = {
  id: 1,
  actor_email: 'admin@example.com',
  action: 'event_deleted',
  target_type: 'event',
  target_id: 5,
  description: 'Deleted event "Durga Puja 2026"',
  created_at: '2026-10-10T18:00:00+00:00',
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAuditLog.mockResolvedValue({
    items: [baseEntry],
    page: 1,
    per_page: 20,
    total: 1,
    total_pages: 1,
  })
})

describe('AdminAuditLogView', () => {
  it('lists entries with actor, human-readable action label, and description', async () => {
    const wrapper = mount(AdminAuditLogView)
    await flushPromises()

    expect(wrapper.text()).toContain('admin@example.com')
    expect(wrapper.text()).toContain('Deleted event "Durga Puja 2026"')
    expect(wrapper.text()).toContain('Event deleted')
    expect(wrapper.text()).not.toContain('event_deleted')
  })

  it('shows an empty state when there are no entries', async () => {
    mockFetchAuditLog.mockResolvedValue({
      items: [], page: 1, per_page: 20, total: 0, total_pages: 0,
    })

    const wrapper = mount(AdminAuditLogView)
    await flushPromises()

    expect(wrapper.text()).toContain('No audit log entries yet.')
  })

  it('shows an error state when the fetch fails', async () => {
    mockFetchAuditLog.mockRejectedValue(new Error('boom'))

    const wrapper = mount(AdminAuditLogView)
    await flushPromises()

    expect(wrapper.text()).toContain('Could not load the audit log.')
  })

  it('reloads with a search query on Enter', async () => {
    const wrapper = mount(AdminAuditLogView)
    await flushPromises()
    mockFetchAuditLog.mockClear()

    await wrapper.find('input').setValue('Durga Puja')
    await wrapper.find('input').trigger('keyup.enter')
    await flushPromises()

    expect(mockFetchAuditLog).toHaveBeenCalledWith(
      expect.objectContaining({ q: 'Durga Puja' }),
    )
  })

  it('reloads with an action filter', async () => {
    const wrapper = mount(AdminAuditLogView)
    await flushPromises()
    mockFetchAuditLog.mockClear()

    await chooseOption(wrapper, 'event_deleted')
    await flushPromises()

    expect(mockFetchAuditLog).toHaveBeenCalledWith(
      expect.objectContaining({ action: ['event_deleted'] }),
    )
  })

  it('disables Previous on page 1, and hides the pager when there is only one page', async () => {
    mockFetchAuditLog.mockResolvedValue({
      items: [baseEntry], page: 1, per_page: 20, total: 40, total_pages: 2,
    })

    const wrapper = mount(AdminAuditLogView)
    await flushPromises()

    const buttons = wrapper.findAll('button')
    expect(buttons.find((b) => b.text() === 'Previous')?.attributes('disabled')).toBeDefined()
    expect(buttons.find((b) => b.text() === 'Next')?.attributes('disabled')).toBeUndefined()

    mockFetchAuditLog.mockResolvedValue({
      items: [baseEntry], page: 1, per_page: 20, total: 1, total_pages: 1,
    })
    const single = mount(AdminAuditLogView)
    await flushPromises()
    expect(single.find('nav[aria-label="Pagination"]').exists()).toBe(false)
  })

  it('requests the next page when Next is clicked', async () => {
    mockFetchAuditLog.mockResolvedValue({
      items: [baseEntry], page: 1, per_page: 20, total: 40, total_pages: 2,
    })

    const wrapper = mount(AdminAuditLogView)
    await flushPromises()
    mockFetchAuditLog.mockClear()

    const next = wrapper.findAll('button').find((b) => b.text() === 'Next')
    await next?.trigger('click')
    await flushPromises()

    expect(mockFetchAuditLog).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2 }),
    )
  })

  it('resets to page 1 when a new search is triggered from a later page', async () => {
    mockFetchAuditLog.mockResolvedValue({
      items: [baseEntry], page: 1, per_page: 20, total: 40, total_pages: 2,
    })

    const wrapper = mount(AdminAuditLogView)
    await flushPromises()

    const next = wrapper.findAll('button').find((b) => b.text() === 'Next')
    await next?.trigger('click')
    await flushPromises()
    mockFetchAuditLog.mockClear()

    await wrapper.find('input').setValue('Durga Puja')
    await wrapper.find('input').trigger('keyup.enter')
    await flushPromises()

    expect(mockFetchAuditLog).toHaveBeenCalledWith(
      expect.objectContaining({ q: 'Durga Puja', page: 1 }),
    )
  })

  it('exports the entries matching the current search and action filter to Excel', async () => {
    const blob = new Blob(['x'])
    mockExportAuditLog.mockResolvedValue(blob)
    const wrapper = mount(AdminAuditLogView)
    await flushPromises()

    await chooseOption(wrapper, 'event_deleted')
    await wrapper.find('input[type="search"]').setValue('Durga')
    await flushPromises()
    await wrapper.find('button.export-audit-log').trigger('click')
    await flushPromises()

    expect(mockExportAuditLog).toHaveBeenCalledWith({ action: ['event_deleted'], q: 'Durga' })
    expect(mockDownloadBlob).toHaveBeenCalledWith(blob, 'audit-log.xlsx')
  })
})
