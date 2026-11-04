// Tests for AdminMembersImportView (5 cases), e.g. AdminMembersImportView; previews an uploaded file and shows valid/invalid counts; confirms only the valid rows and shows the resulting summary.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockPreviewMembersImport = vi.fn()
const mockConfirmMembersImport = vi.fn()
const mockFetchImportHistory = vi.fn()

vi.mock('../../../services/adminImportsApi', () => ({
  previewMembersImport: (...args: unknown[]) => mockPreviewMembersImport(...args),
  confirmMembersImport: (...args: unknown[]) => mockConfirmMembersImport(...args),
  fetchImportHistory: (...args: unknown[]) => mockFetchImportHistory(...args),
}))

import AdminMembersImportView from '../AdminMembersImportView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchImportHistory.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })
})

function selectFile(wrapper: ReturnType<typeof mount>, file: File) {
  const input = wrapper.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [file] })
  return input.trigger('change')
}

describe('AdminMembersImportView', () => {
  it('previews an uploaded file and shows valid/invalid counts', async () => {
    mockPreviewMembersImport.mockResolvedValue({
      rows: [
        { row_number: 1, name: 'Priya Das', email: 'priya@example.com', errors: {} },
        { row_number: 2, name: 'Bad Row', errors: { email: 'This field is required.' } },
      ],
      valid_count: 1,
      invalid_count: 1,
    })

    const wrapper = mount(AdminMembersImportView)
    await flushPromises()

    const file = new File(['data'], 'members.xlsx')
    await selectFile(wrapper, file)
    await flushPromises()

    expect(mockPreviewMembersImport).toHaveBeenCalledWith(file)
    expect(wrapper.text()).toContain('1 valid')
    expect(wrapper.text()).toContain('1 invalid')
    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('This field is required.')
  })

  it('confirms only the valid rows and shows the resulting summary', async () => {
    mockPreviewMembersImport.mockResolvedValue({
      rows: [
        { row_number: 1, name: 'Priya Das', email: 'priya@example.com', membership_type: 'individual', membership_status: 'active', start_date: '2026-01-01', errors: {} },
        { row_number: 2, name: 'Bad Row', errors: { email: 'This field is required.' } },
      ],
      valid_count: 1,
      invalid_count: 1,
    })
    mockConfirmMembersImport.mockResolvedValue({
      id: 1,
      filename: 'members.xlsx',
      admin_email: 'admin@example.com',
      total_rows: 1,
      members_created: 1,
      memberships_created: 1,
      failed_rows: 0,
      created_at: '2026-09-10T10:00:00Z',
    })

    const wrapper = mount(AdminMembersImportView)
    await flushPromises()

    const file = new File(['data'], 'members.xlsx')
    await selectFile(wrapper, file)
    await flushPromises()

    await wrapper.find('button.confirm-import').trigger('click')
    await flushPromises()

    expect(mockConfirmMembersImport).toHaveBeenCalledWith(
      'members.xlsx',
      [expect.objectContaining({ name: 'Priya Das', email: 'priya@example.com' })],
    )
    expect(wrapper.text()).toContain('1 member')
  })

  it('names each row skipped at confirm, with its reason', async () => {
    mockPreviewMembersImport.mockResolvedValue({
      rows: [
        { row_number: 3, name: 'Rohan Das', email: null, parent_email: 'anita@x.no', membership_type: 'child', membership_status: 'active', start_date: '2026-01-01', errors: {} },
      ],
      valid_count: 1,
      invalid_count: 0,
    })
    mockConfirmMembersImport.mockResolvedValue({
      id: 2,
      filename: 'kids.xlsx',
      admin_email: 'admin@example.com',
      total_rows: 1,
      members_created: 0,
      memberships_created: 0,
      failed_rows: 1,
      created_at: '2026-10-06T10:00:00Z',
      failures: [{ row_number: 3, name: 'Rohan Das', reason: 'Parent anita@x.no: This parent has no active (adult) membership.' }],
    })

    const wrapper = mount(AdminMembersImportView)
    await flushPromises()
    await selectFile(wrapper, new File(['data'], 'kids.xlsx'))
    await flushPromises()
    await wrapper.find('button.confirm-import').trigger('click')
    await flushPromises()

    // row_number rides along in the payload so the backend can name the row.
    expect(mockConfirmMembersImport).toHaveBeenCalledWith('kids.xlsx', [expect.objectContaining({ row_number: 3, parent_email: 'anita@x.no' })])
    const list = wrapper.find('.import-failures')
    expect(list.text()).toContain('Row 3 (Rohan Das)')
    expect(list.text()).toContain('no active (adult) membership')
  })

  it('shows recent import history', async () => {
    mockFetchImportHistory.mockResolvedValue({
      items: [
        { id: 1, filename: 'members.xlsx', admin_email: 'admin@example.com', total_rows: 5, members_created: 3, memberships_created: 5, failed_rows: 0, created_at: '2026-09-10T10:00:00Z' },
      ],
      page: 1,
      per_page: 20,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(AdminMembersImportView)
    await flushPromises()

    expect(wrapper.text()).toContain('members.xlsx')
  })
})
