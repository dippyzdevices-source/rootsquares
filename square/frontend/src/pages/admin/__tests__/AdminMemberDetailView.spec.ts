// Tests for AdminMemberDetailView (10 cases), e.g. AdminMemberDetailView; shows the member profile once loaded; shows an empty state when there are no membership records yet.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chooseOption } from '../../../test-utils/baseSelect'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchAdminMember = vi.fn()
const mockUpdateAdminMember = vi.fn()
const mockCreateAdminMembership = vi.fn()
const mockUpdateAdminMembership = vi.fn()
const mockFetchAdminMembershipTypes = vi.fn()
const mockCreateAdminFamilyMember = vi.fn()
const mockUpdateAdminFamilyMember = vi.fn()
const mockDeleteAdminFamilyMember = vi.fn()

vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: vi.fn().mockResolvedValue([
    { value: 'spouse', label: 'Spouse' },
    { value: 'child', label: 'Child' },
    { value: 'parent', label: 'Parent' },
    { value: 'other', label: 'Other' },
  ]),
}))

vi.mock('../../../services/adminMembersApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminMembersApi')>(
    '../../../services/adminMembersApi',
  )
  return {
    ...actual,
    fetchAdminMember: (...args: unknown[]) => mockFetchAdminMember(...args),
    updateAdminMember: (...args: unknown[]) => mockUpdateAdminMember(...args),
    createAdminFamilyMember: (...args: unknown[]) => mockCreateAdminFamilyMember(...args),
    updateAdminFamilyMember: (...args: unknown[]) => mockUpdateAdminFamilyMember(...args),
    deleteAdminFamilyMember: (...args: unknown[]) => mockDeleteAdminFamilyMember(...args),
  }
})

vi.mock('../../../services/adminMembershipsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminMembershipsApi')>(
    '../../../services/adminMembershipsApi',
  )
  return {
    ...actual,
    createAdminMembership: (...args: unknown[]) => mockCreateAdminMembership(...args),
    updateAdminMembership: (...args: unknown[]) => mockUpdateAdminMembership(...args),
  }
})

vi.mock('../../../services/adminMembershipTypesApi', () => ({
  fetchAdminMembershipTypes: (...args: unknown[]) => mockFetchAdminMembershipTypes(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
}))

import AdminMemberDetailView from '../AdminMemberDetailView.vue'

const stubs = { RouterLink: true }

const baseMember = {
  id: 1,
  name: 'Priya Das',
  address: null,
  family_info: null,
  family_members: [],
  email: 'priya@example.com',
  phone: null,
  memberships: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminMembershipTypes.mockResolvedValue({
    items: [
      {
        name: 'individual',
        price: 500,
        billing_frequency: 'yearly',
        contact_for_price: false,
        is_active: true,
        sort_order: 0,
      },
      {
        name: 'family',
        price: 800,
        billing_frequency: 'yearly',
        contact_for_price: false,
        is_active: true,
        sort_order: 1,
      },
    ],
  })
})

describe('AdminMemberDetailView', () => {
  it('shows the member profile once loaded', async () => {
    mockFetchAdminMember.mockResolvedValue(baseMember)

    const wrapper = mount(AdminMemberDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('priya@example.com')
  })

  it('shows an empty state when there are no membership records yet', async () => {
    mockFetchAdminMember.mockResolvedValue(baseMember)

    const wrapper = mount(AdminMemberDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('No membership records yet')
  })

  it('lists existing membership records', async () => {
    mockFetchAdminMember.mockResolvedValue({
      ...baseMember,
      memberships: [
        { id: 1, membership_type: 'individual', status: 'active', start_date: '2026-01-01', end_date: null },
      ],
    })

    const wrapper = mount(AdminMemberDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Individual')
    expect(wrapper.text()).toContain('Active')
  })

  it('saves an edited profile', async () => {
    mockFetchAdminMember.mockResolvedValue(baseMember)
    mockUpdateAdminMember.mockResolvedValue({ ...baseMember, address: 'Oslo, Norway' })

    const wrapper = mount(AdminMemberDetailView, { global: { stubs } })
    await flushPromises()

    await wrapper.findAll('button').find((b) => b.text() === 'Edit profile')!.trigger('click')
    await wrapper.findAll('input')[1].setValue('Oslo, Norway')
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()

    expect(mockUpdateAdminMember).toHaveBeenCalledWith(1, {
      name: 'Priya Das',
      address: 'Oslo, Norway',
    })
  })

  it('creates a new membership record via the modal', async () => {
    mockFetchAdminMember.mockResolvedValue(baseMember)
    mockCreateAdminMembership.mockResolvedValue({
      id: 1,
      membership_type: 'individual',
      status: 'pending',
      start_date: '2026-01-01',
      end_date: null,
    })

    const wrapper = mount(AdminMemberDetailView, { global: { stubs } })
    await flushPromises()

    await wrapper.findAll('button').find((b) => b.text() === 'Add membership')!.trigger('click')

    // BaseModal renders via <Teleport to="body">, outside the mounted wrapper's own subtree.
    const body = new DOMWrapper(document.body)
    await chooseOption(body, 'individual')
    await body.find('input[type="date"]').setValue('2026-01-01')
    await body.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()

    expect(mockCreateAdminMembership).toHaveBeenCalledWith({
      member_id: 1,
      membership_type: 'individual',
      status: 'pending',
      start_date: '2026-01-01',
      end_date: null,
    })

    wrapper.unmount()
  })
})

describe('AdminMemberDetailView — family members', () => {
  it('shows existing family members', async () => {
    mockFetchAdminMember.mockResolvedValue({
      ...baseMember,
      family_members: [{ id: 1, name: 'Anita', relationship_type: 'spouse', age: 34, sort_order: 0 }],
    })

    const wrapper = mount(AdminMemberDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Anita')
    expect(wrapper.text()).toContain('Spouse')
    expect(wrapper.text()).toContain('34')
  })

  it('adds a family member via the modal', async () => {
    mockFetchAdminMember.mockResolvedValue(baseMember)
    mockCreateAdminFamilyMember.mockResolvedValue({ id: 2, name: 'Rohan', relationship_type: 'child', age: 8, sort_order: 0 })

    const wrapper = mount(AdminMemberDetailView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('button.add-family-member').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.find('input').setValue('Rohan')
    await chooseOption(body, 'child')
    await body.find('input[type="number"]').setValue('8')
    await body.find('button.save-family-member').trigger('click')
    await flushPromises()

    expect(mockCreateAdminFamilyMember).toHaveBeenCalledWith(1, {
      name: 'Rohan',
      relationship_type: 'child',
      age: 8,
    })

    wrapper.unmount()
  })

  it('removes a family member', async () => {
    mockFetchAdminMember.mockResolvedValue({
      ...baseMember,
      family_members: [{ id: 1, name: 'Anita', relationship_type: 'spouse', age: 34, sort_order: 0 }],
    })
    mockDeleteAdminFamilyMember.mockResolvedValue(undefined)

    const wrapper = mount(AdminMemberDetailView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('button[aria-label="Remove Anita"]').trigger('click')
    await flushPromises()

    expect(mockDeleteAdminFamilyMember).toHaveBeenCalledWith(1, 1)
  })
})
