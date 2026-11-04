// Tests for RegisterView (26 cases), e.g. RegisterView; calls signUp with email, password, and phone; shows a success message after registering.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

const mockSignUp = vi.fn()
const mockVerifyOtp = vi.fn()
const mockResend = vi.fn()
const mockGetSession = vi.fn()
const mockMode = vi.hoisted(() => ({ value: 'link' as 'code' | 'link' }))

vi.mock('../../../services/supabaseClient', () => ({
  supabase: {
    auth: {
      signUp: (...args: unknown[]) => mockSignUp(...args),
      verifyOtp: (...args: unknown[]) => mockVerifyOtp(...args),
      resend: (...args: unknown[]) => mockResend(...args),
      getSession: (...args: unknown[]) => mockGetSession(...args),
    },
  },
}))

vi.mock('../../../services/authMode', () => ({
  get emailVerificationMode() {
    return mockMode.value
  },
}))

import RegisterView from '../RegisterView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: { template: '<div/>' } },
    { path: '/login', component: { template: '<div/>' } },
  ],
})

const mounted: VueWrapper[] = []

function mountView() {
  const wrapper = mount(RegisterView, { global: { plugins: [router] } })
  mounted.push(wrapper)
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  mockMode.value = 'link'
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
})

afterEach(async () => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.restoreAllMocks()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  await router.push('/')
})

describe('RegisterView', () => {
  it('calls signUp with email, password, and phone', async () => {
    mockSignUp.mockResolvedValue({ error: null })
    const wrapper = mountView()

    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('input[type="tel"]').setValue('+4712345678')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mockSignUp).toHaveBeenCalledWith({
      email: 'a@b.com',
      password: 'secret123',
      options: { data: { phone: '+4712345678' } },
    })
  })

  it('shows a success message after registering', async () => {
    mockSignUp.mockResolvedValue({ error: null })
    const wrapper = mountView()

    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Check your email')
  })

  it('shows an error message when registration fails', async () => {
    mockSignUp.mockResolvedValue({ error: new Error('Email already registered') })
    const wrapper = mountView()

    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Email already registered')
  })
})

describe('RegisterView — code mode (Neon Auth)', () => {
  async function registerIntoCodeStep() {
    mockMode.value = 'code'
    mockSignUp.mockResolvedValue({ error: null })
    mockResend.mockResolvedValue({ error: null })
    const wrapper = mountView()
    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await flushPromises()
    return wrapper
  }

  it('link mode keeps the plain "check your email" message and shows no code field', async () => {
    mockSignUp.mockResolvedValue({ error: null })
    const wrapper = mountView()
    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Check your email')
    expect(wrapper.find('input.code-input').exists()).toBe(false)
    expect(mockResend).not.toHaveBeenCalled()
  })

  it('requests the first code itself right after signing up (Neon sends none on sign-up)', async () => {
    const wrapper = await registerIntoCodeStep()

    expect(mockResend).toHaveBeenCalledTimes(1)
    expect(mockResend).toHaveBeenCalledWith({ type: 'signup', email: 'a@b.com' })
    // ...and the Resend button starts its cooldown as if the user had pressed it.
    expect((wrapper.find('button.resend-code').element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper.text()).toContain('Resend code in 30s')
  })

  it('does not request the first code when sign-up itself fails', async () => {
    mockMode.value = 'code'
    mockSignUp.mockResolvedValue({ error: new Error('Email already registered') })
    const wrapper = mountView()
    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await flushPromises()

    expect(mockResend).not.toHaveBeenCalled()
    expect(wrapper.find('input.code-input').exists()).toBe(false)
    expect(wrapper.text()).toContain('Email already registered')
  })

  it('keeps the code step and lets the user retry at once when the first code cannot be sent', async () => {
    mockMode.value = 'code'
    mockSignUp.mockResolvedValue({ error: null })
    mockResend.mockResolvedValue({ error: new Error('Too many requests') })
    const wrapper = mountView()
    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await flushPromises()

    expect(wrapper.find('input.code-input').exists()).toBe(true)
    expect(wrapper.text()).toContain('Too many requests')
    expect(wrapper.text()).toContain('Resend code')
    // No cooldown after a failure: Resend is usable immediately.
    expect((wrapper.find('button.resend-code').element as HTMLButtonElement).disabled).toBe(false)
  })

  it('swaps the form for a code step after signing up', async () => {
    const wrapper = await registerIntoCodeStep()

    expect(wrapper.find('input.code-input').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('a@b.com')
  })

  it('cannot submit a partly typed code', async () => {
    const wrapper = await registerIntoCodeStep()
    await wrapper.find('input.code-input').setValue('123')

    expect((wrapper.find('button.verify-code').element as HTMLButtonElement).disabled).toBe(true)
  })

  it('accepts a pasted code with spaces or dashes and verifies the 6 digits', async () => {
    // Review Focus #5
    mockVerifyOtp.mockResolvedValue({ error: null })
    mockGetSession.mockResolvedValue({ data: { session: { access_token: 't', user: { id: 'u' } } } })
    const wrapper = await registerIntoCodeStep()

    await wrapper.find('input.code-input').setValue('123 456')
    await wrapper.find('button.verify-code').trigger('click')
    await flushPromises()

    expect(mockVerifyOtp).toHaveBeenCalledWith({ email: 'a@b.com', token: '123456', type: 'signup' })

    await wrapper.find('input.code-input').setValue('123-456')
    expect((wrapper.find('button.verify-code').element as HTMLButtonElement).disabled).toBe(false)
  })

  it('goes to the dashboard when verifying also signed the user in', async () => {
    mockVerifyOtp.mockResolvedValue({ error: null })
    mockGetSession.mockResolvedValue({ data: { session: { access_token: 't', user: { id: 'u' } } } })
    const push = vi.spyOn(router, 'push')
    const wrapper = await registerIntoCodeStep()

    await wrapper.find('input.code-input').setValue('123456')
    await wrapper.find('button.verify-code').trigger('click')
    await flushPromises()

    expect(push).toHaveBeenCalledWith('/')
  })

  it('goes to /login?verified=1 when verifying did not sign the user in', async () => {
    mockVerifyOtp.mockResolvedValue({ error: null })
    mockGetSession.mockResolvedValue({ data: { session: null } })
    const push = vi.spyOn(router, 'push')
    const wrapper = await registerIntoCodeStep()

    await wrapper.find('input.code-input').setValue('123456')
    await wrapper.find('button.verify-code').trigger('click')
    await flushPromises()

    expect(push).toHaveBeenCalledWith({ path: '/login', query: { verified: '1' } })
  })

  it('shows the provider error for a wrong code and keeps the code step open', async () => {
    mockVerifyOtp.mockResolvedValue({ error: new Error('Invalid OTP') })
    const wrapper = await registerIntoCodeStep()

    await wrapper.find('input.code-input').setValue('000000')
    await wrapper.find('button.verify-code').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Invalid OTP')
    expect(wrapper.find('input.code-input').exists()).toBe(true)
    expect((wrapper.find('button.verify-code').element as HTMLButtonElement).disabled).toBe(false)
  })

  it('resend is on a 30 second cooldown, then sends a new code', async () => {
    vi.useFakeTimers()
    mockResend.mockResolvedValue({ error: null })
    mockMode.value = 'code'
    mockSignUp.mockResolvedValue({ error: null })
    const wrapper = mountView()
    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await flushPromises()

    const resend = () => wrapper.find('button.resend-code')
    expect((resend().element as HTMLButtonElement).disabled).toBe(true)

    await vi.advanceTimersByTimeAsync(30_000)
    expect((resend().element as HTMLButtonElement).disabled).toBe(false)

    await resend().trigger('click')
    await flushPromises()

    expect(mockResend).toHaveBeenCalledWith({ type: 'signup', email: 'a@b.com' })
    expect((resend().element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper.text()).toContain('new code')
  })

  it('ignores a second Resend click while the first request is still in flight', async () => {
    vi.useFakeTimers()
    let finishResend!: (value: { error: null }) => void
    // The first call is the automatic send at sign-up; only the manual click afterwards hangs.
    mockResend
      .mockResolvedValueOnce({ error: null })
      .mockReturnValue(new Promise((resolve) => (finishResend = resolve)))
    mockMode.value = 'code'
    mockSignUp.mockResolvedValue({ error: null })
    const wrapper = mountView()
    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await flushPromises()
    mockResend.mockClear()
    await vi.advanceTimersByTimeAsync(30_000)

    const resend = () => wrapper.find('button.resend-code')
    expect((resend().element as HTMLButtonElement).disabled).toBe(false)

    await resend().trigger('click')
    expect((resend().element as HTMLButtonElement).disabled).toBe(true)
    await resend().trigger('click')
    await flushPromises()
    expect(mockResend).toHaveBeenCalledTimes(1)

    finishResend({ error: null })
    await flushPromises()

    expect(mockResend).toHaveBeenCalledTimes(1)
    expect((resend().element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper.text()).toContain('Resend code in 30s')
  })

  it('shows an error if resending fails', async () => {
    vi.useFakeTimers()
    mockResend
      .mockResolvedValueOnce({ error: null })
      .mockResolvedValue({ error: new Error('Too many requests') })
    mockMode.value = 'code'
    mockSignUp.mockResolvedValue({ error: null })
    const wrapper = mountView()
    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[type="password"]').setValue('secret123')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(30_000)

    await wrapper.find('button.resend-code').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Too many requests')
  })

  describe('re-entering the code step via ?verify=<email>', () => {
    async function mountWithQuery(query: string) {
      await router.push(`/${query}`)
      await router.isReady()
      return mountView()
    }

    it('opens the code step with the email prefilled and Resend enabled immediately', async () => {
      mockMode.value = 'code'
      const wrapper = await mountWithQuery('?verify=a@b.com')

      expect(wrapper.find('input.code-input').exists()).toBe(true)
      expect(wrapper.find('input[type="password"]').exists()).toBe(false)
      expect(wrapper.text()).toContain('a@b.com')
      const resend = wrapper.find('button.resend-code')
      expect((resend.element as HTMLButtonElement).disabled).toBe(false)
      expect(resend.text()).toBe('Resend code')
    })

    it('verifies the typed code for the prefilled email', async () => {
      mockMode.value = 'code'
      mockVerifyOtp.mockResolvedValue({ error: null })
      mockGetSession.mockResolvedValue({ data: { session: null } })
      const push = vi.spyOn(router, 'push')
      const wrapper = await mountWithQuery('?verify=a@b.com')

      await wrapper.find('input.code-input').setValue('123456')
      await wrapper.find('button.verify-code').trigger('click')
      await flushPromises()

      expect(mockVerifyOtp).toHaveBeenCalledWith({ email: 'a@b.com', token: '123456', type: 'signup' })
      expect(push).toHaveBeenCalledWith({ path: '/login', query: { verified: '1' } })
    })

    it('resends a code for the prefilled email without needing a password', async () => {
      mockMode.value = 'code'
      mockResend.mockResolvedValue({ error: null })
      const wrapper = await mountWithQuery('?verify=a@b.com')

      await wrapper.find('button.resend-code').trigger('click')
      await flushPromises()

      expect(mockResend).toHaveBeenCalledWith({ type: 'signup', email: 'a@b.com' })
    })

    it('is ignored in link mode', async () => {
      const wrapper = await mountWithQuery('?verify=a@b.com')

      expect(wrapper.find('input.code-input').exists()).toBe(false)
      expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    })

    it.each([
      ['a value with no "@"', '?verify=not-an-email'],
      ['an empty value', '?verify='],
      ['a repeated (array) value', '?verify=a@b.com&verify=c@d.com'],
    ])('is ignored for %s', async (_label, query) => {
      mockMode.value = 'code'
      const wrapper = await mountWithQuery(query)

      expect(wrapper.find('input.code-input').exists()).toBe(false)
      expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    })
  })

  describe('"Sign in instead" footer', () => {
    it('is shown on the form step', async () => {
      mockMode.value = 'code'
      const wrapper = mountView()

      expect(wrapper.text()).toContain('Sign in instead')
    })

    it('is hidden once the code step is open', async () => {
      const wrapper = await registerIntoCodeStep()

      expect(wrapper.find('input.code-input').exists()).toBe(true)
      expect(wrapper.text()).not.toContain('Sign in instead')
      expect(wrapper.text()).not.toContain('Already registered')
    })
  })
})
