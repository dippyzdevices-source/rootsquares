// Tests for MembershipsOff (3 cases), e.g. Memberships module; on: the Become a member button and the membership wording are there; off: no button to the membership page and no membership wording on sig.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Memberships module (W8-R19): no Become a member button, and the sign-in and register texts do not talk about memberships.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/modules')>()),
  moduleEnabled: (key?: string) => !off.keys.includes(key ?? ''),
  offeredPhrase: () => (off.keys.includes('memberships') ? 'events and tickets' : 'events, tickets and membership'),
}))
vi.mock('../../../services/eventsApi', () => ({ fetchEvents: () => Promise.resolve({ items: [] }) }))
vi.mock('../../../services/galleryApi', () => ({ fetchAlbums: () => Promise.resolve({ items: [] }), fetchGalleryMedia: () => Promise.resolve([]) }))
vi.mock('../../../services/newsApi', () => ({ fetchNews: () => Promise.resolve({ items: [] }) }))
vi.mock('../../../services/testimonialsApi', () => ({ fetchTestimonials: () => Promise.resolve({ items: [] }) }))
vi.mock('../../../services/sponsorsApi', () => ({ fetchSponsors: () => Promise.resolve([]) }))
vi.mock('../../../services/supabaseClient', () => ({ supabase: { auth: { signInWithPassword: vi.fn(), signInWithOAuth: vi.fn(), signUp: vi.fn() } } }))
vi.mock('../../../services/authMode', () => ({ emailVerificationMode: 'link' }))
vi.mock('../../../services/siteContent', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../services/siteContent')>()
  return { ...actual, loadHomeContent: () => Promise.resolve(actual.fillHomeContent(undefined)) }
})

import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../HomeView.vue'
import LoginView from '../LoginView.vue'
import RegisterView from '../RegisterView.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }
const router = createRouter({ history: createWebHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div/>' } }] })
const plugins = () => [router, createPinia()]

beforeEach(() => {
  off.keys = []
  setActivePinia(createPinia())
})

describe('Memberships module', () => {
  it('on: the Become a member button and the membership wording are there', async () => {
    const home = mount(HomeView, { global: { stubs, plugins: plugins() } })
    const login = mount(LoginView, { global: { stubs, plugins: plugins() } })
    await flushPromises()
    expect(home.find('a[href="/membership"]').exists()).toBe(true)
    expect(login.text()).toContain('renew your membership')
  })

  it('off: no button to the membership page and no membership wording on sign in or register', async () => {
    off.keys = ['memberships']
    const home = mount(HomeView, { global: { stubs, plugins: plugins() } })
    const login = mount(LoginView, { global: { stubs, plugins: plugins() } })
    const register = mount(RegisterView, { global: { stubs, plugins: plugins() } })
    await flushPromises()
    expect(home.find('a[href="/membership"]').exists()).toBe(false)
    expect(login.text().toLowerCase()).not.toContain('membership')
    expect(register.text().toLowerCase()).not.toContain('membership')
  })
})
