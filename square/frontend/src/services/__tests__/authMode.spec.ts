// Tests for authMode (5 cases), e.g. emailVerificationMode; is 'code' when VITE_AUTH_PROVIDER=neon (Neon Auth); is 'link' when VITE_AUTH_PROVIDER=supabase.
import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('emailVerificationMode', () => {
  it("is 'code' when VITE_AUTH_PROVIDER=neon (Neon Auth)", async () => {
    vi.stubEnv('VITE_AUTH_PROVIDER', 'neon')
    const { emailVerificationMode } = await import('../authMode')
    expect(emailVerificationMode).toBe('code')
  })

  it("is 'link' when VITE_AUTH_PROVIDER=supabase", async () => {
    vi.stubEnv('VITE_AUTH_PROVIDER', 'supabase')
    const { emailVerificationMode } = await import('../authMode')
    expect(emailVerificationMode).toBe('link')
  })

  it("defaults to 'link' when VITE_AUTH_PROVIDER is unset (supabaseClient throws for that case anyway)", async () => {
    vi.stubEnv('VITE_AUTH_PROVIDER', '')
    const { emailVerificationMode } = await import('../authMode')
    expect(emailVerificationMode).toBe('link')
  })

  it('is not driven by VITE_APP_ENV', async () => {
    vi.stubEnv('VITE_AUTH_PROVIDER', 'supabase')
    vi.stubEnv('VITE_APP_ENV', 'development')
    const { emailVerificationMode } = await import('../authMode')
    expect(emailVerificationMode).toBe('link')
  })
})
