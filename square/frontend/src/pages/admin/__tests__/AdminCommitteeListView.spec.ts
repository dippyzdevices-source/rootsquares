// Tests for AdminCommitteeListView (4 cases), e.g. AdminCommitteeListView; lists committee members with role and status; shows an empty state when there are no committee members.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchAdminCommittee = vi.fn()
const mockDeleteAdminCommitteeMember = vi.fn()

vi.mock('../../../services/adminCommitteeApi', () => ({
  fetchAdminCommittee: (...args: unknown[]) => mockFetchAdminCommittee(...args),
  deleteAdminCommitteeMember: (...args: unknown[]) => mockDeleteAdminCommitteeMember(...args),
}))

import AdminCommitteeListView from '../AdminCommitteeListView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AdminCommitteeListView', () => {
  it('lists committee members with role and status', async () => {
    mockFetchAdminCommittee.mockResolvedValue({
      items: [
        { id: 1, name: 'Priya Das', role: 'President', portrait_url: null, address: null, email: null, phone: null, member_since: null, quote: null, display_order: 0, is_active: true, created_at: '', updated_at: '' },
      ],
    })

    const wrapper = mount(AdminCommitteeListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('President')
    expect(wrapper.text()).toContain('Active')
  })

  it('shows an empty state when there are no committee members', async () => {
    mockFetchAdminCommittee.mockResolvedValue({ items: [] })

    const wrapper = mount(AdminCommitteeListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('No committee members yet')
  })

  it('deletes a committee member after confirmation', async () => {
    mockFetchAdminCommittee.mockResolvedValue({
      items: [
        { id: 1, name: 'Priya Das', role: 'President', portrait_url: null, address: null, email: null, phone: null, member_since: null, quote: null, display_order: 0, is_active: true, created_at: '', updated_at: '' },
      ],
    })
    mockDeleteAdminCommitteeMember.mockResolvedValue(undefined)

    const wrapper = mount(AdminCommitteeListView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('button[aria-label="Delete Priya Das"]').trigger('click')
    await flushPromises()
    const body = new DOMWrapper(document.body)
    const confirmButton = body.findAll('button').find((b) => b.text() === 'Delete')
    await confirmButton!.trigger('click')
    await flushPromises()

    expect(mockDeleteAdminCommitteeMember).toHaveBeenCalledWith(1)
    wrapper.unmount()
  })
})
