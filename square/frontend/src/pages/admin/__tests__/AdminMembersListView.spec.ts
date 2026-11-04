// Tests for AdminMembersListView (12 cases), e.g. AdminMembersListView; shows members with their latest membership status; shows an empty state when there is no membership yet.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { chooseOption, optionLabels } from '../../../test-utils/baseSelect'

const mockFetchAdminMembers = vi.fn()
const mockExportMembers = vi.fn()
const mockResendWelcome = vi.fn()

vi.mock('../../../services/adminMembersApi', () => ({
  fetchAdminMembers: (...args: unknown[]) => mockFetchAdminMembers(...args),
  exportMembers: (...args: unknown[]) => mockExportMembers(...args),
  resendMemberWelcomeEmail: (...args: unknown[]) => mockResendWelcome(...args),
}))

const mockUpdateAdminMembership = vi.fn()
vi.mock('../../../services/adminMembershipTypesApi', () => ({
  fetchAdminMembershipTypes: vi.fn().mockResolvedValue({ items: [{ name: 'adult' }, { name: 'child' }] }),
}))

vi.mock('../../../services/adminMembershipsApi', () => ({
  updateAdminMembership: (...args: unknown[]) => mockUpdateAdminMembership(...args),
}))

vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }), useRouter: () => undefined }))

vi.mock('../../../utils/download', () => ({
  downloadBlob: vi.fn(),
}))

import AdminMembersListView from '../AdminMembersListView.vue'

const stubs = { RouterLink: true }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AdminMembersListView', () => {
  it('shows members with their latest membership status', async () => {
    mockFetchAdminMembers.mockResolvedValue({
      items: [
        {
          id: 1,
          name: 'Priya Das',
          email: 'priya@example.com',
          phone: null,
          latest_membership: { membership_type: 'individual', status: 'active' },
        },
      ],
      page: 1,
      per_page: 20,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('priya@example.com')
    expect(wrapper.text()).toContain('Active')
  })

  it('shows an empty state when there is no membership yet', async () => {
    mockFetchAdminMembers.mockResolvedValue({
      items: [{ id: 1, name: 'Priya Das', email: 'priya@example.com', phone: null, latest_membership: null }],
      page: 1,
      per_page: 20,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('No membership yet')
  })

  it('shows an empty state when there are no members', async () => {
    mockFetchAdminMembers.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })

    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('No members found')
  })

  it('re-runs the search when Enter is pressed', async () => {
    mockFetchAdminMembers.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })

    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('input').setValue('rohan')
    await wrapper.find('input').trigger('keyup.enter')
    await flushPromises()

    expect(mockFetchAdminMembers).toHaveBeenLastCalledWith('rohan', '', 20, [], 1, [])
  })

  it('exports members to Excel', async () => {
    mockFetchAdminMembers.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })
    const blob = new Blob(['xlsx-data'])
    mockExportMembers.mockResolvedValue(blob)

    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('button.export-members').trigger('click')
    await flushPromises()

    expect(mockExportMembers).toHaveBeenCalled()
  })

  it('exports with the search that is on screen', async () => {
    mockFetchAdminMembers.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })
    mockExportMembers.mockResolvedValue(new Blob(['xlsx-data']))

    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()
    await wrapper.find('input').setValue('rohan')
    await wrapper.find('input').trigger('keyup.enter')
    await flushPromises()
    await wrapper.find('button.export-members').trigger('click')
    await flushPromises()

    expect(mockExportMembers).toHaveBeenCalledWith({ q: 'rohan', status: [], membershipType: [] })
  })

  it('shows an unpaid self-service request as awaiting payment, with nothing to approve', async () => {
    mockFetchAdminMembers.mockResolvedValue({
      items: [
        {
          id: 1,
          name: 'Priya Das',
          email: 'priya@example.com',
          phone: null,
          latest_membership: { id: 7, membership_type: 'adult', status: 'pending', awaiting_payment: true },
        },
      ],
      page: 1,
      per_page: 20,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.approve-membership').exists()).toBe(false)
    expect(wrapper.text()).toContain('Awaiting payment')
    expect(wrapper.find('.view-member').exists()).toBe(true)
  })

  it('approves a pending latest membership and reloads', async () => {
    mockFetchAdminMembers.mockResolvedValue({
      items: [
        {
          id: 1,
          name: 'Priya Das',
          email: 'priya@example.com',
          phone: null,
          latest_membership: { id: 7, membership_type: 'adult', status: 'pending' },
        },
      ],
      page: 1,
      per_page: 20,
      total: 1,
      total_pages: 1,
    })
    mockUpdateAdminMembership.mockResolvedValue({})

    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()
    await wrapper.find('.approve-membership').trigger('click')
    await flushPromises()

    expect(mockUpdateAdminMembership).toHaveBeenCalledWith(7, { status: 'active' })
    expect(mockFetchAdminMembers).toHaveBeenCalledTimes(2)
  })

  it('filters by membership type, listing the configured types, and starts from page 1', async () => {
    mockFetchAdminMembers.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 1 })
    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()
    mockFetchAdminMembers.mockClear()

    await wrapper.findAll('.base-select-button')[0].trigger('click')
    expect(optionLabels(wrapper, 0)).toEqual(['Adult', 'Child'])
    await chooseOption(wrapper, 'child', 0)
    await flushPromises()

    expect(mockFetchAdminMembers).toHaveBeenLastCalledWith('', '', 20, [], 1, ['child'])
  })

  it('has Export in the page header (like the other lists) and the filters in the toolbar after the search', async () => {
    mockFetchAdminMembers.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 1 })
    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.ds-toolbar button.export-members').exists()).toBe(false)
    expect(wrapper.find('button.export-members').exists()).toBe(true)
    const toolbar = wrapper.find('.ds-toolbar').element
    expect(toolbar.children[0].classList.contains('ds-toolbar-search')).toBe(true)
    expect(toolbar.querySelectorAll('.base-select')).toHaveLength(2)
  })

  it('offers "Resend welcome email" only for members who have an email address', async () => {
    mockFetchAdminMembers.mockResolvedValue({
      items: [
        { id: 1, name: 'Priya Das', email: 'priya@example.com', phone: null, latest_membership: null },
        { id: 2, name: 'No Email', email: null, phone: null, latest_membership: null },
      ],
      page: 1, per_page: 20, total: 2, total_pages: 1,
    })
    mockResendWelcome.mockResolvedValue({ sent_to: 'priya@example.com' })
    const wrapper = mount(AdminMembersListView, { global: { stubs } })
    await flushPromises()

    const buttons = wrapper.findAll('button.resend-welcome')
    expect(buttons).toHaveLength(1)
    await buttons[0].trigger('click')
    await flushPromises()
    expect(mockResendWelcome).toHaveBeenCalledWith(1)
  })
})
