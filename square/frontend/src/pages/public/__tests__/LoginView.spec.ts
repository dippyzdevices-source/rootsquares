// Tests for LoginView (11 cases), e.g. LoginView; calls signInWithPassword with the entered credentials; shows an error message when login fails.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

const mockSignInWithPassword = vi.fn()
const mockSignInWithOAuth = vi.fn()
const mockMode = vi.hoisted(() => ({ value: 'link' as 'code' | 'link' }))

vi.mock('../../../services/supabaseClient', () => ({
  supabase: {
    auth: {
      signInWithPassword: (...args: unknown[]) => mockSignInWithPassword(...args),
      signInWithOAuth: (...args: unknown[]) => mockSignInWithOAuth(...args),
    },
  },
}))

vi.mock('../../../services/authMode', () => ({
  get emailVerificationMode() {
    return mockMode.value
  },
}))

import LoginView from '../LoginView.vue'

async function mountView(initialUrl = '/') {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/login', component: { template: '<div/>' } },
      { path: '/register', component: { template: '<div/>' } },
    ],
  })
  await router.push(initialUrl)
  await router.isReady()
  return mount(LoginView, { global: { plugins: [router] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  mockMode.value = 'link'
})

describe('LoginView', () => {
  it('calls signInWithPassword with the entered credentials', async () => {
    mockSignInWithPassword.mockResolvedValue({ error: null })
    const wrapper = await mountView()

    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mockSignInWithPassword).toHaveBeenCalledWith({ email: 'a@b.com', password: 'secret123' })
  })

  it('shows an error message when login fails', async () => {
    mockSignInWithPassword.mockResolvedValue({ error: new Error('Invalid credentials') })
    const wrapper = await mountView()

    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('wrong')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Invalid credentials')
  })

  it('calls signInWithOAuth with google when the Google button is clicked', async () => {
    mockSignInWithOAuth.mockResolvedValue({ error: null })
    const wrapper = await mountView()

    await wrapper.find('button.ds-google-btn').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mockSignInWithOAuth).toHaveBeenCalledWith(
      expect.objectContaining({ provider: 'google' }),
    )
  })

  it('shows an "email verified" notice when arriving from the code step', async () => {
    const wrapper = await mountView('/login?verified=1')

    expect(wrapper.text()).toContain('Email verified')
  })

  it('shows no verified notice on a plain visit', async () => {
    const wrapper = await mountView('/login')

    expect(wrapper.text()).not.toContain('Email verified')
  })

  describe('unverified-email recovery link', () => {
    async function failSignInWith(message: string) {
      mockSignInWithPassword.mockResolvedValue({ error: new Error(message) })
      const wrapper = await mountView()
      await wrapper.find('input[type="email"]').setValue('a@b.com')
      await wrapper.find('input[type="password"]').setValue('secret123')
      await wrapper.find('button.ds-btn-primary').trigger('click')
      await flushPromises()
      return wrapper
    }

    it('in code mode, an "Email not verified" failure links to the code step for that email', async () => {
      mockMode.value = 'code'
      const wrapper = await failSignInWith('Email not verified')

      const link = wrapper.findAll('a').find((a) => a.text() === 'Enter your verification code')
      expect(link).toBeDefined()
      expect(decodeURIComponent(link!.attributes('href')!)).toBe('/register?verify=a@b.com')
    })

    it('in code mode, any other failure shows no such link', async () => {
      mockMode.value = 'code'
      const wrapper = await failSignInWith('Invalid password')

      expect(wrapper.text()).toContain('Invalid password')
      expect(wrapper.text()).not.toContain('Enter your verification code')
    })

    it('in link mode, an "Email not verified" failure shows no such link', async () => {
      const wrapper = await failSignInWith('Email not verified')

      expect(wrapper.text()).toContain('Email not verified')
      expect(wrapper.text()).not.toContain('Enter your verification code')
    })

    it('clears the link when the next attempt fails for a different reason', async () => {
      mockMode.value = 'code'
      const wrapper = await failSignInWith('Email not verified')
      expect(wrapper.text()).toContain('Enter your verification code')

      mockSignInWithPassword.mockResolvedValue({ error: new Error('Invalid password') })
      await wrapper.find('button.ds-btn-primary').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Invalid password')
      expect(wrapper.text()).not.toContain('Enter your verification code')
    })
  })
})

describe('LoginView: Google sign-in (W23-R86)', () => {
  it('is offered only when Google is switched on for the square, so nobody ends on the provider\'s error page', async () => {
    const { squareProfile } = await import('../../../services/squareConfig')
    const on = await mountView()
    expect(on.text()).toContain('Continue with Google')
    expect(on.find('.ds-or-rule').exists()).toBe(true)
    squareProfile.googleLogin = false
    try {
      const off = await mountView()
      expect(off.text()).not.toContain('Continue with Google')
      expect(off.find('.ds-google-btn').exists()).toBe(false)
      expect(off.find('.ds-or-rule').exists()).toBe(false) // no dangling "or" above the e-mail form
      expect(off.text()).toContain('Email') // the e-mail form is still there
    } finally {
      squareProfile.googleLogin = true
    }
  })
})
