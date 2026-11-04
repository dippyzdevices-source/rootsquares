// Tests for supabaseClient (6 cases), e.g. supabaseClient facade; exports the real Supabase client when VITE_AUTH_PROVIDER=supabase; exports the Neon Auth adapter when VITE_AUTH_PROVIDER=neon.
import { afterEach, describe, expect, it, vi } from 'vitest'

// Vitest loads the developer's own frontend/.env, so every test stubs all three provider vars
// explicitly (an empty string counts as unset) instead of relying on them being absent.
function stubAuthEnv(provider: string, url: string, publicKey = '') {
  vi.stubEnv('VITE_AUTH_PROVIDER', provider)
  vi.stubEnv('VITE_AUTH_URL', url)
  vi.stubEnv('VITE_AUTH_PUBLIC_KEY', publicKey)
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('supabaseClient facade', () => {
  it('exports the real Supabase client when VITE_AUTH_PROVIDER=supabase', async () => {
    stubAuthEnv('supabase', 'https://example.supabase.co', 'anon-key')

    const { supabase } = await import('../supabaseClient')

    // The real @supabase/supabase-js client exposes .auth.signInWithOtp, which the
    // MiniAuthClient interface (and the Neon adapter) deliberately does not implement.
    expect(typeof (supabase.auth as { signInWithOtp?: unknown }).signInWithOtp).toBe('function')
  })

  it('exports the Neon Auth adapter when VITE_AUTH_PROVIDER=neon', async () => {
    stubAuthEnv('neon', 'https://example-neon-auth.tech')

    const { supabase } = await import('../supabaseClient')

    expect((supabase.auth as { signInWithOtp?: unknown }).signInWithOtp).toBeUndefined()
    expect(typeof supabase.auth.getSession).toBe('function')
  })

  it('is not driven by VITE_APP_ENV — the provider comes from VITE_AUTH_PROVIDER alone', async () => {
    // Prod can run either provider, so the environment name must not pick one.
    stubAuthEnv('supabase', 'https://example.supabase.co', 'anon-key')
    vi.stubEnv('VITE_APP_ENV', 'development')

    const { supabase } = await import('../supabaseClient')

    expect(typeof (supabase.auth as { signInWithOtp?: unknown }).signInWithOtp).toBe('function')
  })

  it('throws a clear error when VITE_AUTH_PROVIDER is missing', async () => {
    stubAuthEnv('', 'https://example.supabase.co', 'anon-key')

    await expect(import('../supabaseClient')).rejects.toThrow(/VITE_AUTH_PROVIDER/)
  })

  it('throws a clear error when VITE_AUTH_PROVIDER is not a known provider', async () => {
    stubAuthEnv('firebase', 'https://example.firebase.co')

    await expect(import('../supabaseClient')).rejects.toThrow(/VITE_AUTH_PROVIDER/)
  })

  it.each(['supabase', 'neon'])('throws a clear error when VITE_AUTH_URL is empty for %s', async (provider) => {
    stubAuthEnv(provider, '', 'anon-key')

    await expect(import('../supabaseClient')).rejects.toThrow(/VITE_AUTH_URL/)
  })
})
