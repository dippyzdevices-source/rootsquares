// Tests for AdminFoundersListView (4 cases), e.g. AdminFoundersListView; lists founders with role and status; shows an empty state when there are no founders.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchAdminFounders = vi.fn()
const mockDeleteAdminFounder = vi.fn()

vi.mock('../../../services/adminFoundersApi', () => ({
  fetchAdminFounders: (...args: unknown[]) => mockFetchAdminFounders(...args),
  deleteAdminFounder: (...args: unknown[]) => mockDeleteAdminFounder(...args),
}))

import AdminFoundersListView from '../AdminFoundersListView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AdminFoundersListView', () => {
  it('lists founders with role and status', async () => {
    mockFetchAdminFounders.mockResolvedValue({
      items: [
        { id: 1, name: 'Priya Das', role: 'President', portrait_url: null, sub_name: null, quote: 'q', display_order: 0, is_active: true, created_at: '', updated_at: '' },
      ],
    })

    const wrapper = mount(AdminFoundersListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('President')
    expect(wrapper.text()).toContain('Active')
  })

  it('shows an empty state when there are no founders', async () => {
    mockFetchAdminFounders.mockResolvedValue({ items: [] })

    const wrapper = mount(AdminFoundersListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('No founders yet')
  })

  it('deletes a founder after confirmation', async () => {
    mockFetchAdminFounders.mockResolvedValue({
      items: [
        { id: 1, name: 'Priya Das', role: 'President', portrait_url: null, sub_name: null, quote: 'q', display_order: 0, is_active: true, created_at: '', updated_at: '' },
      ],
    })
    mockDeleteAdminFounder.mockResolvedValue(undefined)

    const wrapper = mount(AdminFoundersListView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('button[aria-label="Delete Priya Das"]').trigger('click')
    await flushPromises()
    const body = new DOMWrapper(document.body)
    const confirmButton = body.findAll('button').find((b) => b.text() === 'Delete')
    await confirmButton!.trigger('click')
    await flushPromises()

    expect(mockDeleteAdminFounder).toHaveBeenCalledWith(1)
    wrapper.unmount()
  })
})
