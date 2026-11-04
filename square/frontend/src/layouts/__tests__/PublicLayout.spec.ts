// Tests for PublicLayout (14 cases), e.g. PublicLayout; hides the mobile nav by default; shows the mobile nav after the hamburger button is clicked.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import PublicLayout from '../PublicLayout.vue'
import { useAuthStore } from '../../stores/auth'
import type { Session } from '@supabase/supabase-js'
import { setAdminPreview } from '../../composables/useAdminPreview'

vi.mock('../../services/supabaseClient', () => ({
  supabase: { auth: { signOut: vi.fn().mockResolvedValue({ error: null }) } },
}))

const stubs = { RouterLink: true, RouterView: true }

function mountLayout() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/', component: { template: '<div/>' } }],
  })
  return mount(PublicLayout, { global: { stubs, plugins: [router] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('PublicLayout', () => {
  it('hides the mobile nav by default', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('header').findAll('nav')).toHaveLength(1)
  })

  it('shows the mobile nav after the hamburger button is clicked', async () => {
    const wrapper = mountLayout()

    await wrapper.find('button[aria-label="Toggle navigation"]').trigger('click')

    expect(wrapper.find('header').findAll('nav')).toHaveLength(2)
  })

  it('hides the mobile nav again after a second click', async () => {
    const wrapper = mountLayout()
    const button = wrapper.find('button[aria-label="Toggle navigation"]')

    await button.trigger('click')
    await button.trigger('click')

    expect(wrapper.find('header').findAll('nav')).toHaveLength(1)
  })

  it('shows an explicit link to the member portal, named by the account, as the first line of the mobile menu', async () => {
    const authStore = useAuthStore()
    authStore.session = {
      access_token: 'token-123',
      user: { user_metadata: { full_name: 'Priya Das' } },
    } as unknown as Session
    authStore.user = { id: 1, email: 'member@example.com', phone: null, role: 'member' }

    const router = createRouter({
      history: createWebHistory(),
      routes: [{ path: '/', component: { template: '<div/>' } }],
    })
    const wrapper = mount(PublicLayout, {
      global: {
        stubs: { RouterLink: { template: '<a><slot /></a>' }, RouterView: true },
        plugins: [router],
      },
    })
    await wrapper.find('button[aria-label="Toggle navigation"]').trigger('click')

    const mobileNav = wrapper.find('header').findAll('nav')[1]
    // The account name (not a generic "Dashboard" label) is the first line — verifies it's
    // an explicit, directly-tappable link, not just a bare avatar, and not nested behind a
    // second disclosure like AccountMenu (which would hide it behind another tap).
    expect(mobileNav.text().indexOf('Priya Das')).toBe(0)
  })

  it('shows a Login link when not authenticated', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('router-link-stub[to="/login"]').exists()).toBe(true)
    expect(wrapper.findAll('button').some((btn) => btn.text().includes('Logout'))).toBe(false)
  })

  it('shows both an Admin link and a My Account link when authenticated as an admin', async () => {
    const authStore = useAuthStore()
    authStore.session = { access_token: 'token-123' } as unknown as Session
    authStore.user = { id: 1, email: 'admin@example.com', phone: null, role: 'admin' }

    const wrapper = mountLayout()

    // The utility bar's "My portal" link is always visible; the Admin console item lives in
    // the account menu's dropdown panel, which only mounts once opened.
    expect(wrapper.find('router-link-stub[to="/member"]').exists()).toBe(true)
    await wrapper.find('button[aria-haspopup="menu"]').trigger('click')
    expect(wrapper.find('router-link-stub[to="/admin"]').exists()).toBe(true)
  })

  it('shows a My Account link when authenticated as a non-admin member', () => {
    const authStore = useAuthStore()
    authStore.session = { access_token: 'token-123' } as unknown as Session
    authStore.user = { id: 1, email: 'member@example.com', phone: null, role: 'member' }

    const wrapper = mountLayout()

    expect(wrapper.find('router-link-stub[to="/member"]').exists()).toBe(true)
    expect(wrapper.find('router-link-stub[to="/admin"]').exists()).toBe(false)
  })

  it('shows a Check-in link for a volunteer but not for a plain member', async () => {
    const authStore = useAuthStore()
    authStore.session = { access_token: 'token-123' } as unknown as Session
    authStore.user = { id: 1, email: 'volunteer@example.com', phone: null, role: 'volunteer' }

    const wrapper = mountLayout()
    await wrapper.find('button[aria-haspopup="menu"]').trigger('click')

    expect(wrapper.find('router-link-stub[to="/checkin"]').exists()).toBe(true)
  })

  it('hides the Check-in link for a plain member', () => {
    const authStore = useAuthStore()
    authStore.session = { access_token: 'token-123' } as unknown as Session
    authStore.user = { id: 1, email: 'member@example.com', phone: null, role: 'member' }

    const wrapper = mountLayout()

    expect(wrapper.find('router-link-stub[to="/checkin"]').exists()).toBe(false)
  })

  it('shows neither an Admin nor My Account link when not authenticated', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('router-link-stub[to="/admin"]').exists()).toBe(false)
    expect(wrapper.find('router-link-stub[to="/member"]').exists()).toBe(false)
  })

  it("shows the Google account's display name instead of plain 'My Account' text", async () => {
    const authStore = useAuthStore()
    authStore.session = {
      access_token: 'token-123',
      user: { user_metadata: { full_name: 'Priya Das', avatar_url: 'https://example.com/pic.jpg' } },
    } as unknown as Session
    authStore.user = { id: 1, email: 'priya@example.com', phone: null, role: 'member' }

    const router = createRouter({
      history: createWebHistory(),
      routes: [{ path: '/', component: { template: '<div/>' } }],
    })
    const wrapper = mount(PublicLayout, {
      global: {
        stubs: { RouterLink: { template: '<a><slot /></a>' }, RouterView: true },
        plugins: [router],
      },
    })

    // The account menu's trigger shows only the first name — the full name renders in the
    // dropdown panel, which mounts only once opened (matching the design system's AccountMenu).
    expect(wrapper.text()).not.toContain('My Account')
    expect(wrapper.find(`img[src="https://example.com/pic.jpg"]`).exists()).toBe(true)

    await wrapper.find('button[aria-haspopup="menu"]').trigger('click')

    expect(wrapper.text()).toContain('Priya Das')
  })

  it("falls back to 'My Account' text for a plain email/password account", () => {
    const authStore = useAuthStore()
    authStore.session = { access_token: 'token-123', user: { user_metadata: {} } } as unknown as Session
    authStore.user = { id: 1, email: 'priya@example.com', phone: null, role: 'member' }

    const router = createRouter({
      history: createWebHistory(),
      routes: [{ path: '/', component: { template: '<div/>' } }],
    })
    const wrapper = mount(PublicLayout, {
      global: {
        stubs: { RouterLink: { template: '<a><slot /></a>' }, RouterView: true },
        plugins: [router],
      },
    })

    expect(wrapper.text()).toContain('My Account')
  })

  it('shows the Admin preview banner only while an admin preview is active', async () => {
    setAdminPreview(false)
    const wrapper = mountLayout()
    expect(wrapper.find('.admin-preview-banner').exists()).toBe(false)

    setAdminPreview(true)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.admin-preview-banner').text()).toContain('Admin preview')

    setAdminPreview(false)
  })
})
