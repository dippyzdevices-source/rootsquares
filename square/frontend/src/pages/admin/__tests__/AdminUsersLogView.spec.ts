// Tests for AdminUsersLogView (4 cases), e.g. AdminUsersLogView; lists everyone who signed in, linking those on the member list and fla; shows an empty state when nobody has signed in.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchUsers = vi.fn()
const mockResend = vi.fn()

vi.mock('../../../services/adminUsersApi', () => ({
  fetchSignedInUsers: (...args: unknown[]) => mockFetchUsers(...args),
  resendWelcomeEmail: (...args: unknown[]) => mockResend(...args),
}))

import AdminUsersLogView from '../AdminUsersLogView.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }
const page = (items: unknown[]) => ({ items, page: 1, per_page: 20, total: items.length, total_pages: 1 })

let wrapper: ReturnType<typeof mount> | null = null
beforeEach(() => vi.clearAllMocks())
afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('AdminUsersLogView', () => {
  it('lists everyone who signed in, linking those on the member list and flagging those who are not', async () => {
    mockFetchUsers.mockResolvedValue(page([
      { id: 1, email: 'a@x.no', role: 'member', auth_provider: 'supabase', member_id: 7, member_name: 'Anna Roy', first_sign_in: '2026-10-18T15:21:30+00:00' },
      { id: 2, email: 'b@x.no', role: 'admin', auth_provider: 'neon', member_id: null, member_name: null, first_sign_in: '2026-10-17T10:00:00+00:00' },
    ]))
    wrapper = mount(AdminUsersLogView, { global: { stubs } })
    await flushPromises()

    expect(mockFetchUsers).toHaveBeenCalledWith(expect.objectContaining({ page: 1, perPage: 20 }))
    const rows = wrapper.findAll('table.users-log tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('a@x.no')
    expect(rows[0].find('a').attributes('href')).toBe('/admin/members/7')
    expect(rows[1].text()).toContain('Not on the member list')
  })

  it('shows an empty state when nobody has signed in', async () => {
    mockFetchUsers.mockResolvedValue(page([]))
    wrapper = mount(AdminUsersLogView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Nobody has signed in yet')
  })

  it('resends the welcome email for a user and uses the Profile column name', async () => {
    mockFetchUsers.mockResolvedValue(page([
      { id: 1, email: 'a@x.no', role: 'member', auth_provider: 'supabase', member_id: null, member_name: null, first_sign_in: '2026-10-18T15:21:30+00:00' },
    ]))
    mockResend.mockResolvedValue({ sent_to: 'a@x.no' })
    wrapper = mount(AdminUsersLogView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('table.users-log thead').text()).toContain('Profile')
    await wrapper.find('button.resend-welcome').trigger('click')
    await flushPromises()
    expect(mockResend).toHaveBeenCalledWith(1)
  })
})
