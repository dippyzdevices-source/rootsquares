// Tests for AdminLayout (9 cases), e.g. AdminLayout; renders the shared site header; renders the shared site footer.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import AdminLayout from '../AdminLayout.vue'

vi.mock('../../services/supabaseClient', () => ({
  supabase: { auth: { signOut: vi.fn().mockResolvedValue({ error: null }) } },
}))

const mockFetchAdminEvents = vi.fn()
const mockFetchAdminMembers = vi.fn()
const mockFetchAdminMemberships = vi.fn()
const mockFetchAdminTickets = vi.fn()
const mockFetchAdminOrders = vi.fn()
const mockFetchAdminPayments = vi.fn()
const mockFetchAdminAlbums = vi.fn()
const mockFetchAdminNews = vi.fn()
const mockFetchAdminTestimonials = vi.fn()
const mockFetchAdminUsers = vi.fn()

vi.mock('../../services/adminEventsApi', () => ({ fetchAdminEvents: (...args: unknown[]) => mockFetchAdminEvents(...args) }))
vi.mock('../../services/adminMembersApi', () => ({ fetchAdminMembers: (...args: unknown[]) => mockFetchAdminMembers(...args) }))
vi.mock('../../services/adminMembershipsApi', () => ({ fetchAdminMemberships: (...args: unknown[]) => mockFetchAdminMemberships(...args) }))
vi.mock('../../services/adminTicketsApi', () => ({ fetchAdminTickets: (...args: unknown[]) => mockFetchAdminTickets(...args) }))
vi.mock('../../services/adminOrdersApi', () => ({ fetchAdminOrders: (...args: unknown[]) => mockFetchAdminOrders(...args) }))
vi.mock('../../services/adminPaymentsApi', () => ({ fetchAdminPayments: (...args: unknown[]) => mockFetchAdminPayments(...args) }))
vi.mock('../../services/adminGalleryApi', () => ({ fetchAdminAlbums: (...args: unknown[]) => mockFetchAdminAlbums(...args) }))
vi.mock('../../services/adminNewsApi', () => ({ fetchAdminNews: (...args: unknown[]) => mockFetchAdminNews(...args) }))
vi.mock('../../services/adminTestimonialsApi', () => ({ fetchAdminTestimonials: (...args: unknown[]) => mockFetchAdminTestimonials(...args) }))
vi.mock('../../services/adminUsersApi', async () => {
  const actual = await vi.importActual<typeof import('../../services/adminUsersApi')>('../../services/adminUsersApi')
  return { ...actual, fetchAdminUsers: (...args: unknown[]) => mockFetchAdminUsers(...args) }
})

const stubs = { RouterLink: { template: '<a><slot /></a>' }, RouterView: true }

function makeRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div/>' } }],
  })
}

function mountLayout() {
  return mount(AdminLayout, { global: { stubs, plugins: [makeRouter()] } })
}

// Mounts at a given admin path (waits for the router to settle) and returns which sidebar items are lit.
async function activeLabels(path: string): Promise<string[]> {
  const router = makeRouter()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(AdminLayout, { global: { stubs, plugins: [router] } })
  await flushPromises()
  return wrapper.findAll('.ds-appshell__link-active').map((link) => link.text().replace(/[0-9]+$/, '').trim())
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  mockFetchAdminEvents.mockResolvedValue({ items: [], page: 1, per_page: 1, total: 4, total_pages: 4 })
  mockFetchAdminMembers.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 41, total_pages: 3 })
  mockFetchAdminMemberships.mockResolvedValue({ items: [], page: 1, per_page: 1, total: 12, total_pages: 12 })
  mockFetchAdminTickets.mockResolvedValue({ items: [], page: 1, per_page: 1, total: 30, total_pages: 30 })
  mockFetchAdminOrders.mockResolvedValue({ items: [], page: 1, per_page: 1, total: 9, total_pages: 9 })
  mockFetchAdminPayments.mockResolvedValue({ items: [], page: 1, per_page: 1, total: 15, total_pages: 15 })
  mockFetchAdminAlbums.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 5, total_pages: 1 })
  mockFetchAdminNews.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 7, total_pages: 1 })
  mockFetchAdminTestimonials.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 3, total_pages: 1 })
  mockFetchAdminUsers.mockResolvedValue({ items: [], page: 1, per_page: 1, total: 6, total_pages: 6 })
})

describe('AdminLayout', () => {
  it('renders the shared site header', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('header').exists()).toBe(true)
  })

  it('renders the shared site footer', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('footer').exists()).toBe(true)
  })

  it('renders one sidebar nav link per admin section', () => {
    const wrapper = mountLayout()

    expect(wrapper.findAll('.ds-appshell__links a')).toHaveLength(17)
  })

  it('includes a sidebar link to every real admin route', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('.ds-appshell__links a[to="/admin/events"]').exists()).toBe(true)
    expect(wrapper.find('.ds-appshell__links a[to="/admin/audit-log"]').exists()).toBe(true)
    expect(wrapper.find('.ds-appshell__links a[to="/admin/content"]').exists()).toBe(true)
    expect(wrapper.find('.ds-appshell__links a[to="/admin/accounting"]').exists()).toBe(true)
  })

  it('shows a live item count badge on sections that have one', async () => {
    const wrapper = mountLayout()
    await flushPromises()

    const eventsLink = wrapper.find('a[to="/admin/events"]')
    expect(eventsLink.find('.ds-appshell__link-count').text()).toBe('4')
    const membersLink = wrapper.find('a[to="/admin/members"]')
    expect(membersLink.find('.ds-appshell__link-count').text()).toBe('41')
    const volunteersLink = wrapper.find('a[to="/admin/volunteers"]')
    expect(volunteersLink.find('.ds-appshell__link-count').text()).toBe('6')
    expect(mockFetchAdminUsers).toHaveBeenCalledWith(undefined, 'volunteer', 1)
  })

  it('does not show a count badge on sections without one', async () => {
    const wrapper = mountLayout()
    await flushPromises()

    const checkinLink = wrapper.find('a[to="/admin/checkin"]')
    expect(checkinLink.find('.ds-appshell__link-count').exists()).toBe(false)
  })

  it('keeps the News item lit on the Magazines tab and on article forms, and no other item', async () => {
    expect(await activeLabels('/admin/news/magazines')).toEqual(['News'])
    expect(await activeLabels('/admin/news/new')).toEqual(['News'])
  })

  it('keeps Newsletter and Members lit across their sub-pages', async () => {
    expect(await activeLabels('/admin/newsletter/issues/3')).toEqual(['Newsletter'])
    expect(await activeLabels('/admin/membership-types')).toEqual(['Members'])
    expect(await activeLabels('/admin/members/duplicates')).toEqual(['Members'])
  })
})
