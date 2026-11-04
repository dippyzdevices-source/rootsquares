// The Members area without the Memberships module is a plain list of people (W11-R25, ADR 044): no membership column or filters, 'People' wording,
// and an 'Add person' action that creates no membership.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminMembers = vi.fn()
const mockAddAdminMember = vi.fn()

vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => key !== 'memberships' })) // Memberships is off
vi.mock('../../../services/adminMembersApi', () => {
  class DuplicateMemberError extends Error {
    memberId = 0
  }
  class ValidationError extends Error {
    errors: Record<string, string> = {}
  }
  return {
    fetchAdminMembers: (...args: unknown[]) => mockFetchAdminMembers(...args),
    exportMembers: vi.fn(),
    addAdminMember: (...args: unknown[]) => mockAddAdminMember(...args),
    DuplicateMemberError,
    ValidationError,
  }
})
vi.mock('../../../services/adminMembershipTypesApi', () => ({ fetchAdminMembershipTypes: vi.fn().mockRejectedValue(new Error('404')) }))
vi.mock('../../../services/adminMembershipsApi', () => ({ updateAdminMembership: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }), useRouter: () => undefined }))
vi.mock('../../../utils/download', () => ({ downloadBlob: vi.fn() }))

import AdminMembersListView from '../AdminMembersListView.vue'

const stubs = { RouterLink: true }

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminMembers.mockResolvedValue({
    items: [{ id: 1, name: 'Sam Helper', email: 'sam@example.com', phone: null, latest_membership: null }],
    page: 1,
    per_page: 20,
    total: 1,
    total_pages: 1,
  })
})

describe('AdminMembersListView without Memberships', () => {
  it('says People, has no membership column and no membership filters', async () => {
    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('h1').text()).toBe('People')
    expect(wrapper.text()).toContain('Sam Helper')
    expect(wrapper.text()).not.toContain('Membership')
    expect(wrapper.text()).not.toContain('No membership yet')
    expect(wrapper.find('[aria-label="Filter by membership status"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Filter by membership type"]').exists()).toBe(false)
  })

  it('adds a person by hand and reloads the list', async () => {
    mockAddAdminMember.mockResolvedValue({ id: 2, name: 'New Person' })
    const wrapper = mount(AdminMembersListView, { global: { stubs }, attachTo: document.body })
    await flushPromises()
    await wrapper.find('button.add-person').trigger('click')
    const input = document.body.querySelector('.ds-modal input[type="text"]') as HTMLInputElement
    input.value = '  New Person '
    input.dispatchEvent(new Event('input'))
    await flushPromises()
    ;(document.body.querySelector('.ds-modal form') as HTMLFormElement).dispatchEvent(new Event('submit', { cancelable: true }))
    await flushPromises()
    expect(mockAddAdminMember).toHaveBeenCalledWith({ name: 'New Person', email: undefined, phone: undefined })
    expect(mockFetchAdminMembers).toHaveBeenCalledTimes(2) // first load and the reload after adding
    wrapper.unmount()
  })
})
