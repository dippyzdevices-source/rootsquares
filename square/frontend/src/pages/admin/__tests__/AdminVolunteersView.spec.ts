// Tests for AdminVolunteersView (9 cases), e.g. AdminVolunteersView; lists users with their current role and linked member name; shows a helpful empty state when a search matches no one.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchAdminUsers = vi.fn()
const mockUpdateAdminUserRole = vi.fn()
const mockFetchAdminUserEvents = vi.fn()
const mockSetAdminUserEvents = vi.fn()

vi.mock('../../../services/adminUsersApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminUsersApi')>(
    '../../../services/adminUsersApi',
  )
  return {
    ...actual,
    fetchAdminUsers: (...args: unknown[]) => mockFetchAdminUsers(...args),
    updateAdminUserRole: (...args: unknown[]) => mockUpdateAdminUserRole(...args),
    fetchAdminUserEvents: (...args: unknown[]) => mockFetchAdminUserEvents(...args),
    setAdminUserEvents: (...args: unknown[]) => mockSetAdminUserEvents(...args),
  }
})

import AdminVolunteersView from '../AdminVolunteersView.vue'
import { useToast } from '../../../composables/useToast'

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminUsers.mockResolvedValue({
    items: [
      { id: 1, email: 'priya@example.com', role: 'member', member_name: 'Priya Das' },
      { id: 2, email: 'rohan@example.com', role: 'volunteer', member_name: null },
    ],
    page: 1, per_page: 20, total: 2, total_pages: 1,
  })
})

describe('AdminVolunteersView', () => {
  it('lists users with their current role and linked member name', async () => {
    const wrapper = mount(AdminVolunteersView)
    await flushPromises()

    expect(wrapper.text()).toContain('priya@example.com')
    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('rohan@example.com')
    expect(wrapper.text()).toContain('Volunteer')
  })

  it('shows a helpful empty state when a search matches no one', async () => {
    mockFetchAdminUsers.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })

    const wrapper = mount(AdminVolunteersView)
    await flushPromises()

    expect(wrapper.text()).toContain('No matching user found')
    expect(wrapper.text()).toContain("hasn't logged in yet")
  })

  it('promotes a member to volunteer', async () => {
    mockUpdateAdminUserRole.mockResolvedValue({ id: 1, email: 'priya@example.com', role: 'volunteer' })

    const wrapper = mount(AdminVolunteersView)
    await flushPromises()

    await wrapper.find('button[aria-label="Make Priya Das a volunteer"]').trigger('click')
    await flushPromises()

    expect(mockUpdateAdminUserRole).toHaveBeenCalledWith(1, 'volunteer')
  })

  it('reverts a volunteer to member', async () => {
    mockUpdateAdminUserRole.mockResolvedValue({ id: 2, email: 'rohan@example.com', role: 'member' })

    const wrapper = mount(AdminVolunteersView)
    await flushPromises()

    await wrapper.find('button[aria-label="Revert rohan@example.com to member"]').trigger('click')
    await flushPromises()

    expect(mockUpdateAdminUserRole).toHaveBeenCalledWith(2, 'member')
  })

  it('stops loading and shows a toast when the initial fetch fails', async () => {
    mockFetchAdminUsers.mockRejectedValue(new Error('Failed to fetch users: 500'))
    const toast = useToast()
    toast.toasts.splice(0, toast.toasts.length)

    const wrapper = mount(AdminVolunteersView)
    await flushPromises()

    expect(wrapper.text()).not.toContain('Loading users')
    expect(toast.toasts.some((t) => t.variant === 'error')).toBe(true)
  })

  it('only shows "Assign events" for volunteers, not members', async () => {
    const wrapper = mount(AdminVolunteersView)
    await flushPromises()

    expect(wrapper.find('button[aria-label^="Assign Check-in access to Priya Das"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label^="Assign Check-in access to rohan@example.com"]').exists()).toBe(true)
  })

  it('opens the assign-events modal pre-checked with the volunteer\'s current assignments', async () => {
    mockFetchAdminUserEvents.mockResolvedValue({
      events: [
        { id: 1, title: 'Durga Puja 2026', start_datetime: '2026-10-10T10:00:00Z' },
        { id: 2, title: 'Saraswati Puja 2026', start_datetime: '2027-02-01T10:00:00Z' },
      ],
      assigned_event_ids: [1],
    })

    const wrapper = mount(AdminVolunteersView)
    await flushPromises()
    await wrapper.find('button[aria-label^="Assign Check-in access to rohan@example.com"]').trigger('click')
    await flushPromises()

    expect(mockFetchAdminUserEvents).toHaveBeenCalledWith(2)
    const modal = new DOMWrapper(document.body)
    expect(modal.text()).toContain('Durga Puja 2026')
    expect(modal.text()).toContain('Saraswati Puja 2026')
    const checkboxes = modal.findAll('input[type="checkbox"]')
    expect((checkboxes[0].element as HTMLInputElement).checked).toBe(true)
    expect((checkboxes[1].element as HTMLInputElement).checked).toBe(false)
    wrapper.unmount()
  })

  it('saves the toggled event assignment set', async () => {
    mockFetchAdminUserEvents.mockResolvedValue({
      events: [{ id: 1, title: 'Durga Puja 2026', start_datetime: '2026-10-10T10:00:00Z' }],
      assigned_event_ids: [],
    })
    mockSetAdminUserEvents.mockResolvedValue({ assigned_event_ids: [1] })

    const wrapper = mount(AdminVolunteersView)
    await flushPromises()
    await wrapper.find('button[aria-label^="Assign Check-in access to rohan@example.com"]').trigger('click')
    await flushPromises()

    const modal = new DOMWrapper(document.body)
    await modal.find('input[type="checkbox"]').setValue(true)
    await modal.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()

    expect(mockSetAdminUserEvents).toHaveBeenCalledWith(2, [1])
    wrapper.unmount()
  })
})
