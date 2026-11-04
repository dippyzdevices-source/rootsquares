// Tests for auth (17 cases), e.g. useAuthStore; starts unauthenticated when there is no existing session; fetches the local user profile when a session exists.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockGetSession = vi.fn()
const mockOnAuthStateChange = vi.fn()
const mockSignUp = vi.fn()
const mockSignInWithPassword = vi.fn()
const mockSignInWithOAuth = vi.fn()
const mockSignOut = vi.fn()
const mockResetPasswordForEmail = vi.fn()
const mockUpdateUser = vi.fn()
const mockVerifyOtp = vi.fn()
const mockResend = vi.fn()

vi.mock('../../services/supabaseClient', () => ({
  supabase: {
    auth: {
      getSession: (...args: unknown[]) => mockGetSession(...args),
      onAuthStateChange: (...args: unknown[]) => mockOnAuthStateChange(...args),
      signUp: (...args: unknown[]) => mockSignUp(...args),
      signInWithPassword: (...args: unknown[]) => mockSignInWithPassword(...args),
      signInWithOAuth: (...args: unknown[]) => mockSignInWithOAuth(...args),
      signOut: (...args: unknown[]) => mockSignOut(...args),
      resetPasswordForEmail: (...args: unknown[]) => mockResetPasswordForEmail(...args),
      updateUser: (...args: unknown[]) => mockUpdateUser(...args),
      verifyOtp: (...args: unknown[]) => mockVerifyOtp(...args),
      resend: (...args: unknown[]) => mockResend(...args),
    },
  },
}))

import { useAuthStore } from '../auth'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  mockGetSession.mockResolvedValue({ data: { session: null } })
  mockOnAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } })
})

describe('useAuthStore', () => {
  it('starts unauthenticated when there is no existing session', async () => {
    const store = useAuthStore()

    await store.initialize()

    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
  })

  it('fetches the local user profile when a session exists', async () => {
    mockGetSession.mockResolvedValue({
      data: { session: { access_token: 'token-123' } },
    })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, email: 'a@b.com', phone: null, role: 'member' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const store = useAuthStore()
    await store.initialize()

    expect(store.isAuthenticated).toBe(true)
    expect(store.user).toEqual({ id: 1, email: 'a@b.com', phone: null, role: 'member' })
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/me'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )

    vi.unstubAllGlobals()
  })

  it('isAdmin reflects the local user role', async () => {
    mockGetSession.mockResolvedValue({ data: { session: { access_token: 'token-123' } } })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: 1, email: 'a@b.com', phone: null, role: 'admin' }),
      }),
    )

    const store = useAuthStore()
    await store.initialize()

    expect(store.isAdmin).toBe(true)

    vi.unstubAllGlobals()
  })

  it('isVolunteer reflects the local user role', async () => {
    mockGetSession.mockResolvedValue({ data: { session: { access_token: 'token-123' } } })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: 1, email: 'a@b.com', phone: null, role: 'volunteer' }),
      }),
    )

    const store = useAuthStore()
    await store.initialize()

    expect(store.isVolunteer).toBe(true)
    expect(store.isAdmin).toBe(false)

    vi.unstubAllGlobals()
  })

  it('signInWithPassword throws when Supabase returns an error', async () => {
    mockSignInWithPassword.mockResolvedValue({ error: new Error('Invalid credentials') })
    const store = useAuthStore()

    await expect(store.signInWithPassword('a@b.com', 'wrong')).rejects.toThrow(
      'Invalid credentials',
    )
  })

  it('signUp passes phone through as user metadata', async () => {
    mockSignUp.mockResolvedValue({ error: null })
    const store = useAuthStore()

    await store.signUp('a@b.com', 'secret123', '+4712345678')

    expect(mockSignUp).toHaveBeenCalledWith({
      email: 'a@b.com',
      password: 'secret123',
      options: { data: { phone: '+4712345678' } },
    })
  })

  it('initialize is memoized so concurrent calls only run setup once', async () => {
    // Regression test: the router guard calls initialize() on every navigation. It must
    // be memoized so a hard reload of a protected route (which races the guard's first
    // call against anything else awaiting initialize()) doesn't re-run getSession()/
    // subscribe to onAuthStateChange multiple times.
    const store = useAuthStore()

    await Promise.all([store.initialize(), store.initialize(), store.initialize()])

    expect(mockGetSession).toHaveBeenCalledTimes(1)
    expect(mockOnAuthStateChange).toHaveBeenCalledTimes(1)
  })

  it('avatarUrl and displayName read from Google user_metadata when present', () => {
    const store = useAuthStore()
    store.session = {
      access_token: 'x',
      user: {
        user_metadata: { avatar_url: 'https://example.com/pic.jpg', full_name: 'Priya Das' },
      },
    } as never

    expect(store.avatarUrl).toBe('https://example.com/pic.jpg')
    expect(store.displayName).toBe('Priya Das')
  })

  it('avatarUrl and displayName are null for a plain email/password account', () => {
    const store = useAuthStore()
    store.session = { access_token: 'x', user: { user_metadata: {} } } as never

    expect(store.avatarUrl).toBeNull()
    expect(store.displayName).toBeNull()
  })

  it('signOut clears session and user', async () => {
    mockSignOut.mockResolvedValue({ error: null })
    const store = useAuthStore()
    store.session = { access_token: 'x' } as never
    store.user = { id: 1, email: 'a@b.com', phone: null, role: 'member' }

    await store.signOut()

    expect(store.session).toBeNull()
    expect(store.user).toBeNull()
  })

  it('verifyEmailCode verifies the code, then reports whether a session now exists', async () => {
    mockVerifyOtp.mockResolvedValue({ error: null })
    mockGetSession.mockResolvedValue({ data: { session: { access_token: 't', user: { id: 'u1' } } } })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
    const store = useAuthStore()

    const signedIn = await store.verifyEmailCode('a@b.com', '123456')

    expect(mockVerifyOtp).toHaveBeenCalledWith({ email: 'a@b.com', token: '123456', type: 'signup' })
    expect(signedIn).toBe(true)
    expect(store.isAuthenticated).toBe(true)
    vi.unstubAllGlobals()
  })

  it('verifyEmailCode returns false when verifying did not create a session', async () => {
    mockVerifyOtp.mockResolvedValue({ error: null })
    mockGetSession.mockResolvedValue({ data: { session: null } })
    const store = useAuthStore()

    expect(await store.verifyEmailCode('a@b.com', '123456')).toBe(false)
    expect(store.isAuthenticated).toBe(false)
  })

  it('verifyEmailCode still succeeds when loading the local profile fails afterwards', async () => {
    // The code is already consumed once verifyOtp succeeds — a network/CORS failure fetching
    // /api/auth/me must not be reported as a failed verification.
    mockVerifyOtp.mockResolvedValue({ error: null })
    mockGetSession.mockResolvedValue({ data: { session: { access_token: 't', user: { id: 'u1' } } } })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
    try {
      const store = useAuthStore()

      await expect(store.verifyEmailCode('a@b.com', '123456')).resolves.toBe(true)
      expect(store.isAuthenticated).toBe(true)
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('verifyEmailCode throws the provider error for a wrong code', async () => {
    mockVerifyOtp.mockResolvedValue({ error: new Error('Invalid OTP') })
    const store = useAuthStore()

    await expect(store.verifyEmailCode('a@b.com', '000000')).rejects.toThrow('Invalid OTP')
  })

  it('resendVerificationCode asks the provider to resend the signup code', async () => {
    mockResend.mockResolvedValue({ error: null })
    const store = useAuthStore()

    await store.resendVerificationCode('a@b.com')

    expect(mockResend).toHaveBeenCalledWith({ type: 'signup', email: 'a@b.com' })
  })

  it('resendVerificationCode throws the provider error', async () => {
    mockResend.mockResolvedValue({ error: new Error('Too many requests') })
    const store = useAuthStore()

    await expect(store.resendVerificationCode('a@b.com')).rejects.toThrow('Too many requests')
  })
})
