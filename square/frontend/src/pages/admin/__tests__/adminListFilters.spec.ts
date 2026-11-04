// Every admin list page has the same toolbar: status pills first, then the search. This spec mounts
// each one and checks the pills, the search and (client pages) the filtering, or (server pages) the
// parameters sent to the API.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import type { Component } from 'vue'

const m = vi.hoisted(() => ({
  albums: vi.fn(),
  news: vi.fn(),
  users: vi.fn(),
  committee: vi.fn(),
  founders: vi.fn(),
  sponsors: vi.fn(),
  magazines: vi.fn(),
  issues: vi.fn(),
  types: vi.fn(),
  followUp: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }), useRouter: () => ({ push: vi.fn() }) }))
vi.mock('../../../services/adminGalleryApi', async (orig) => ({ ...(await orig<object>()), fetchAdminAlbums: (...a: unknown[]) => m.albums(...a) }))
vi.mock('../../../services/adminNewsApi', async (orig) => ({ ...(await orig<object>()), fetchAdminNews: (...a: unknown[]) => m.news(...a) }))
vi.mock('../../../services/adminUsersApi', async (orig) => ({ ...(await orig<object>()), fetchAdminUsers: (...a: unknown[]) => m.users(...a) }))
vi.mock('../../../services/adminCommitteeApi', async (orig) => ({ ...(await orig<object>()), fetchAdminCommittee: () => m.committee() }))
vi.mock('../../../services/adminFoundersApi', async (orig) => ({ ...(await orig<object>()), fetchAdminFounders: () => m.founders() }))
vi.mock('../../../services/adminSponsorsApi', async (orig) => ({ ...(await orig<object>()), fetchAdminSponsors: () => m.sponsors() }))
vi.mock('../../../services/adminMagazinesApi', async (orig) => ({ ...(await orig<object>()), fetchAdminMagazines: () => m.magazines() }))
vi.mock('../../../services/messagesApi', async (orig) => ({ ...(await orig<object>()), fetchMessages: () => m.issues() }))
vi.mock('../../../services/adminMembershipTypesApi', async (orig) => ({ ...(await orig<object>()), fetchAdminMembershipTypes: () => m.types() }))
vi.mock('../../../services/adminMembershipFollowUpApi', async (orig) => ({ ...(await orig<object>()), fetchFollowUp: () => m.followUp() }))

import AdminGalleryListView from '../AdminGalleryListView.vue'
import AdminNewsListView from '../AdminNewsListView.vue'
import AdminVolunteersView from '../AdminVolunteersView.vue'
import AdminCommitteeListView from '../AdminCommitteeListView.vue'
import AdminFoundersListView from '../AdminFoundersListView.vue'
import AdminSponsorsListView from '../AdminSponsorsListView.vue'
import AdminMagazinesListView from '../AdminMagazinesListView.vue'
import AdminNewsletterIssuesView from '../AdminNewsletterIssuesView.vue'
import AdminMembershipTypesView from '../AdminMembershipTypesView.vue'
import AdminMembersFollowUpView from '../AdminMembersFollowUpView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' }, 'router-link': { template: '<a><slot /></a>' } }
const page = { page: 1, per_page: 20, total: 3, total_pages: 1 }

beforeEach(() => {
  vi.clearAllMocks()
  m.albums.mockResolvedValue({ items: [{ id: 1, title: 'Durga Puja 2025', description: null, event_id: null, category: null, year: 2025, published: true, created_at: '', updated_at: '', media: [] }], ...page })
  m.news.mockResolvedValue({ items: [{ id: 1, title: 'Mahalaya recap', slug: 'm', status: 'published', category: null, author: null, summary: null, published_at: null, created_at: '', updated_at: '' }], ...page })
  m.users.mockResolvedValue({ items: [{ id: 1, email: 'priya@example.com', role: 'member', member_name: 'Priya Das' }], ...page })
  m.committee.mockResolvedValue({ items: [
    { id: 1, name: 'Anita Roy', sub_name: null, role: 'President', is_active: true },
    { id: 2, name: 'Bimal Sen', sub_name: null, role: 'Treasurer', is_active: false },
  ] })
  m.founders.mockResolvedValue({ items: [
    { id: 1, name: 'Founder One', sub_name: null, role: 'Founder', is_active: true },
    { id: 2, name: 'Founder Two', sub_name: null, role: 'Co-founder', is_active: false },
  ] })
  m.sponsors.mockResolvedValue({ items: [
    { id: 1, name: 'Acme AS', logo_url: null, website_url: 'https://acme.no', is_active: true },
    { id: 2, name: 'Beta Ltd', logo_url: null, website_url: null, is_active: false },
  ] })
  m.magazines.mockResolvedValue({ items: [
    { id: 1, title: 'Sharad 2026', slug: 's', issue_label: 'Autumn', issue_date: null, published: true, updated_at: '' },
    { id: 2, title: 'Spring Draft', slug: 'sd', issue_label: null, issue_date: null, published: false, updated_at: '' },
  ] })
  m.issues.mockResolvedValue({ total: 2, items: [
    { id: 1, subject: 'Puja greetings', status: 'sent', sent_count: 10, recipients_total: 10, skipped_count: 0, failed_count: 0, sent_at: '2026-10-01T10:00:00Z', scheduled_for: null, created_at: '2026-10-01T09:00:00Z' },
    { id: 2, subject: 'Next month plans', status: 'draft', sent_count: 0, recipients_total: 0, skipped_count: 0, failed_count: 0, sent_at: null, scheduled_for: null, created_at: '2026-10-02T09:00:00Z' },
  ] })
  m.types.mockResolvedValue({ items: [
    { name: 'adult', price: 300, billing_frequency: 'yearly', contact_for_price: false, is_active: true, sort_order: 0 },
    { name: 'family', price: 500, billing_frequency: 'yearly', contact_for_price: false, is_active: false, sort_order: 1 },
  ] })
  m.followUp.mockResolvedValue({
    requests: [
      { membership_id: 1, member_id: 1, name: 'Priya Das', email: 'priya@example.com', phone: null, membership_type: 'adult', period_label: '2026', amount: 30000, requested_at: '2026-10-01', days_waiting: 3, can_remind: true, last_reminded_at: null },
    ],
    dues: [
      { membership_id: 2, member_id: 2, name: 'Arjun Sen', email: 'arjun@example.com', phone: null, membership_type: 'adult', due_count: 1, due_total: 30000, days_overdue: 5, can_remind: true, last_reminded_at: null },
    ],
  })
})

async function open(view: Component) {
  const wrapper = mount(view, { global: { stubs } })
  await flushPromises()
  return wrapper
}

const pill = (wrapper: ReturnType<typeof mount>, label: string) => wrapper.findAll('.ds-toolbar-pills .ds-tag').find((b) => b.text() === label)!

describe('every list page: status pills first, then the search', () => {
  const pages: [string, Component, string[]][] = [
    ['Gallery', AdminGalleryListView, ['All', 'Published', 'Draft']],
    ['News', AdminNewsListView, ['All', 'Published', 'Scheduled', 'Draft', 'Archived']],
    ['Volunteers', AdminVolunteersView, ['All', 'Volunteers', 'Members']],
    ['Committee', AdminCommitteeListView, ['All', 'Active', 'Hidden']],
    ['Founders', AdminFoundersListView, ['All', 'Active', 'Hidden']],
    ['Sponsors', AdminSponsorsListView, ['All', 'Active', 'Hidden']],
    ['Magazines', AdminMagazinesListView, ['All', 'Published', 'Draft']],
    ['Newsletter issues', AdminNewsletterIssuesView, ['All', 'Draft', 'Scheduled', 'Sending', 'Sent']],
    ['Membership types', AdminMembershipTypesView, ['All', 'Active', 'Inactive']],
  ]
  it.each(pages)('%s', async (_name, view, labels) => {
    const wrapper = await open(view)
    const toolbar = wrapper.find('.ds-toolbar').element
    expect(toolbar.children[0].classList.contains('ds-toolbar-pills')).toBe(true)
    expect(toolbar.children[1].classList.contains('ds-toolbar-search')).toBe(true)
    expect(wrapper.findAll('.ds-toolbar-pills .ds-tag').map((b) => b.text())).toEqual(labels)
    expect(wrapper.find('input[type="search"]').exists()).toBe(true)
  })
})

describe('server-paged pages send the filter and search to the API, starting from page 1', () => {
  it('Gallery: published / draft + title', async () => {
    const wrapper = await open(AdminGalleryListView)
    m.albums.mockClear()
    await pill(wrapper, 'Draft').trigger('click')
    await flushPromises()
    expect(m.albums).toHaveBeenLastCalledWith(20, 1, { q: undefined, published: false })

    await wrapper.find('input[type="search"]').setValue('durga')
    await wrapper.find('input[type="search"]').trigger('keyup', { key: 'Enter' })
    await flushPromises()
    expect(m.albums).toHaveBeenLastCalledWith(20, 1, { q: 'durga', published: false })
  })

  it('News: status + text', async () => {
    const wrapper = await open(AdminNewsListView)
    m.news.mockClear()
    await pill(wrapper, 'Scheduled').trigger('click')
    await flushPromises()
    expect(m.news).toHaveBeenLastCalledWith(20, 1, { q: undefined, status: 'scheduled' })

    await wrapper.find('input[type="search"]').setValue('recap')
    await wrapper.find('input[type="search"]').trigger('keyup', { key: 'Enter' })
    await flushPromises()
    expect(m.news).toHaveBeenLastCalledWith(20, 1, { q: 'recap', status: 'scheduled' })
  })

  it('Volunteers: role pill + search', async () => {
    const wrapper = await open(AdminVolunteersView)
    m.users.mockClear()
    await pill(wrapper, 'Volunteers').trigger('click')
    await flushPromises()
    expect(m.users).toHaveBeenLastCalledWith(undefined, 'volunteer', 20, 1)

    await wrapper.find('input[type="search"]').setValue('priya')
    await wrapper.find('input[type="search"]').trigger('keyup', { key: 'Enter' })
    await flushPromises()
    expect(m.users).toHaveBeenLastCalledWith('priya', 'volunteer', 20, 1)
  })
})

describe('client pages filter the list they already hold', () => {
  it('Committee: Hidden pill, then a role search', async () => {
    const wrapper = await open(AdminCommitteeListView)
    expect(wrapper.text()).toContain('Anita Roy')
    expect(wrapper.text()).toContain('Bimal Sen')

    await pill(wrapper, 'Hidden').trigger('click')
    expect(wrapper.text()).not.toContain('Anita Roy')
    expect(wrapper.text()).toContain('Bimal Sen')

    await pill(wrapper, 'All').trigger('click')
    await wrapper.find('input[type="search"]').setValue('president')
    expect(wrapper.text()).toContain('Anita Roy')
    expect(wrapper.text()).not.toContain('Bimal Sen')

    await wrapper.find('input[type="search"]').setValue('zzz')
    expect(wrapper.text()).toContain('Nothing matches this filter or search.')
  })

  it('Founders and Sponsors: Active / Hidden', async () => {
    const founders = await open(AdminFoundersListView)
    await pill(founders, 'Active').trigger('click')
    expect(founders.text()).toContain('Founder One')
    expect(founders.text()).not.toContain('Founder Two')

    const sponsors = await open(AdminSponsorsListView)
    await pill(sponsors, 'Hidden').trigger('click')
    expect(sponsors.text()).toContain('Beta Ltd')
    expect(sponsors.text()).not.toContain('Acme AS')
    await pill(sponsors, 'All').trigger('click')
    await sponsors.find('input[type="search"]').setValue('acme.no')
    expect(sponsors.text()).toContain('Acme AS')
    expect(sponsors.text()).not.toContain('Beta Ltd')
  })

  it('Magazines: Published / Draft + title or issue', async () => {
    const wrapper = await open(AdminMagazinesListView)
    await pill(wrapper, 'Draft').trigger('click')
    expect(wrapper.text()).toContain('Spring Draft')
    expect(wrapper.text()).not.toContain('Sharad 2026')
    await pill(wrapper, 'All').trigger('click')
    await wrapper.find('input[type="search"]').setValue('autumn')
    expect(wrapper.text()).toContain('Sharad 2026')
    expect(wrapper.text()).not.toContain('Spring Draft')
  })

  it('Newsletter issues: status pill + subject', async () => {
    const wrapper = await open(AdminNewsletterIssuesView)
    await pill(wrapper, 'Sent').trigger('click')
    expect(wrapper.text()).toContain('Puja greetings')
    expect(wrapper.text()).not.toContain('Next month plans')
    await pill(wrapper, 'All').trigger('click')
    await wrapper.find('input[type="search"]').setValue('next month')
    expect(wrapper.text()).toContain('Next month plans')
    expect(wrapper.text()).not.toContain('Puja greetings')
  })

  it('Membership types: Active / Inactive + name', async () => {
    const wrapper = await open(AdminMembershipTypesView)
    await pill(wrapper, 'Inactive').trigger('click')
    expect(wrapper.text()).toContain('Family')
    expect(wrapper.text()).not.toContain('Adult')
    await pill(wrapper, 'All').trigger('click')
    await wrapper.find('input[type="search"]').setValue('adul')
    expect(wrapper.text()).toContain('Adult')
    expect(wrapper.text()).not.toContain('Family')
  })

  it('Awaiting payment: one search narrows both tables by name or email', async () => {
    const wrapper = await open(AdminMembersFollowUpView)
    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('Arjun Sen')

    await wrapper.find('input[type="search"]').setValue('arjun@')
    expect(wrapper.text()).not.toContain('Priya Das')
    expect(wrapper.text()).toContain('Arjun Sen')
    expect(wrapper.text()).toContain('No requests match this search.')

    await wrapper.find('input[type="search"]').setValue('priya')
    expect(wrapper.text()).toContain('Priya Das')
    expect(wrapper.text()).toContain('No members match this search.')
  })
})
