// The member page without the Memberships module is a person's page (W11-R26, ADR 044): profile only, no family and no membership history, no types request.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminMember = vi.fn()
const mockFetchAdminMembershipTypes = vi.fn()

vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => key !== 'memberships' })) // Memberships is off
vi.mock('../../../services/lookupsApi', () => ({ fetchLookup: vi.fn().mockResolvedValue([{ value: 'child', label: 'Child' }]) }))
vi.mock('../../../services/adminMembersApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminMembersApi')>('../../../services/adminMembersApi')
  return { ...actual, fetchAdminMember: (...args: unknown[]) => mockFetchAdminMember(...args) }
})
vi.mock('../../../services/adminMembershipTypesApi', () => ({ fetchAdminMembershipTypes: (...args: unknown[]) => mockFetchAdminMembershipTypes(...args) }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { id: '1' } }) }))

import AdminMemberDetailView from '../AdminMemberDetailView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminMember.mockResolvedValue({
    id: 1,
    name: 'Sam Helper',
    address: null,
    photo_url: null,
    family_info: null,
    family_members: [],
    parent: null,
    children: [],
    email: 'sam@example.com',
    phone: null,
    memberships: [],
  })
})

describe('AdminMemberDetailView without Memberships', () => {
  it('shows the person, but no family, no membership history and no membership-types request', async () => {
    const wrapper = mount(AdminMemberDetailView, { global: { stubs: { RouterLink: true } } })
    await flushPromises()
    expect(wrapper.find('h1').text()).toBe('People')
    expect(wrapper.text()).toContain('Sam Helper')
    expect(wrapper.text()).not.toContain('Family')
    expect(wrapper.text()).not.toContain('Add family member')
    expect(wrapper.text()).not.toContain('Membership history')
    expect(wrapper.text()).not.toContain('Add membership')
    expect(mockFetchAdminMembershipTypes).not.toHaveBeenCalled()
  })
})
