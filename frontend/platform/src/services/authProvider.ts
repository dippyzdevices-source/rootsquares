// Sign-in through an external identity provider (ADR 028): Supabase Auth in local/test, Neon Auth in production. The provider issues the
// JWT, the platform API only verifies it (Authorization: Bearer). Off by default: with no VITE_AUTH_PROVIDER the app uses the platform's own
// cookie login. The provider libraries are loaded on first use, so they are not part of the main bundle.
// Adapted from the bca-oslo reference (frontend/src/services/supabaseClient.ts, neonAuthAdapter.ts).

/** A failed provider call (wrong password, unverified email, ...). `message` comes from the provider and is shown to the user. */
export class ProviderError extends Error {
  readonly code = 'provider_error'
}

export interface ProviderClient {
  /** signedIn is false when the provider first wants the email address verified. */
  signUp(input: { email: string; password: string; name: string }): Promise<{ signedIn: boolean }>
  signIn(email: string, password: string): Promise<void>
  /** Leaves for Google and returns to redirectTo with a session (the caller's page is gone, the promise only settles on failure). */
  signInWithGoogle(redirectTo: string): Promise<void>
  /** Email a reset link that lands on redirectTo. Succeeds whether or not the address has an account. */
  requestPasswordReset(email: string, redirectTo: string): Promise<void>
  /** True when the page was opened from a reset link (Supabase: a recovery session exists; Neon: the address carries the token). */
  hasRecoverySession(): Promise<boolean>
  updatePassword(newPassword: string): Promise<void>
  signOut(): Promise<void>
  accessToken(): Promise<string | null>
}

const name = ((import.meta.env.VITE_AUTH_PROVIDER as string | undefined) ?? '').trim()
const url = ((import.meta.env.VITE_AUTH_URL as string | undefined) ?? '').trim().replace(/\/$/, '')
const publicKey = ((import.meta.env.VITE_AUTH_PUBLIC_KEY as string | undefined) ?? '').trim()

if (name && name !== 'supabase' && name !== 'neon') throw new Error(`VITE_AUTH_PROVIDER must be "supabase" or "neon" (got "${name}"). See frontend/.env.example.`)
if (name && !url) throw new Error('VITE_AUTH_URL is required when VITE_AUTH_PROVIDER is set. See frontend/.env.example.')
if (name === 'supabase' && !publicKey) throw new Error('VITE_AUTH_PUBLIC_KEY (the Supabase publishable key) is required for supabase. See frontend/.env.example.')

/** True when a provider is configured (never in the in-browser mock, which has no real accounts). */
export const providerEnabled = name !== '' && import.meta.env.VITE_USE_MOCK !== 'true'
export const providerName = name

let client: Promise<ProviderClient> | null = null
export function getProvider(): Promise<ProviderClient> {
  if (!providerEnabled) return Promise.reject(new ProviderError('Sign-in with a provider is not configured'))
  client ??= name === 'neon'
    ? import('./authProviderNeon').then((m) => m.createNeonClient(url))
    : import('./authProviderSupabase').then((m) => m.createSupabaseClient(url, publicKey))
  return client
}

// The token is reused until shortly before it expires (Neon's session call is a network request, and every API call needs the token).
let cached: { token: string; expiresAt: number } | null = null
const SKEW_MS = 30_000

function expiryOf(token: string): number {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]!.replace(/-/g, '+').replace(/_/g, '/'))) as { exp?: number }
    return payload.exp ? payload.exp * 1000 : 0
  } catch {
    return 0
  }
}

/** The current provider JWT, or null when no provider is configured or nobody is signed in with it. Never throws. */
export async function providerToken(): Promise<string | null> {
  if (!providerEnabled) return null
  if (cached && cached.expiresAt - SKEW_MS > Date.now()) return cached.token
  try {
    const token = await (await getProvider()).accessToken()
    cached = token ? { token, expiresAt: expiryOf(token) } : null
    return token
  } catch {
    cached = null
    return null
  }
}

export const forgetProviderToken = () => { cached = null }
