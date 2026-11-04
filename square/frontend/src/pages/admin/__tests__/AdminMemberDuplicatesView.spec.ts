// Tests for AdminMemberDuplicatesView (3 cases), e.g. AdminMemberDuplicatesView; shows an empty state when there are no duplicates; merges the other records into the kept one after confirming.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchDuplicates = vi.fn()
const mockMerge = vi.fn()

vi.mock('../../../services/adminMembersApi', () => ({
  fetchDuplicateMembers: (...args: unknown[]) => mockFetchDuplicates(...args),
  mergeAdminMember: (...args: unknown[]) => mockMerge(...args),
}))

import AdminMemberDuplicatesView from '../AdminMemberDuplicatesView.vue'

const stubs = { RouterLink: true }
const group = {
  reason: 'email',
  members: [
    { id: 1, name: 'Priya Das', email: 'p@x.no', phone: null, latest_membership: null },
    { id: 2, name: 'Priya D', email: 'P@x.no', phone: null, latest_membership: null },
  ],
}

let wrapper: ReturnType<typeof mount> | null = null

beforeEach(() => {
  vi.clearAllMocks()
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('AdminMemberDuplicatesView', () => {
  it('shows an empty state when there are no duplicates', async () => {
    mockFetchDuplicates.mockResolvedValue({ groups: [] })
    wrapper = mount(AdminMemberDuplicatesView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('No duplicates found')
  })

  it('merges the other records into the kept one after confirming', async () => {
    mockFetchDuplicates.mockResolvedValueOnce({ groups: [group] }).mockResolvedValue({ groups: [] })
    mockMerge.mockResolvedValue({})
    wrapper = mount(AdminMemberDuplicatesView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Same email')
    await wrapper.findAll('.keep-member')[0].trigger('click')
    await flushPromises()
    await new DOMWrapper(document.body).find('.confirm-merge').trigger('click')
    await flushPromises()

    expect(mockMerge).toHaveBeenCalledWith(1, 2)
    expect(mockFetchDuplicates).toHaveBeenCalledTimes(2)
  })
})
