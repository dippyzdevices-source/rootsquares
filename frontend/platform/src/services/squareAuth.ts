// Signing in to ONE square with that square's own auth project (ADR 028), never with the platform's. The project url and its publishable key come
// from the public square data (both are public by design). The Supabase library is loaded on first use.
import type { SupabaseClient } from '@supabase/supabase-js'

const clients = new Map<string, Promise<SupabaseClient>>()

/** One client per square; it also reads a session out of the address when the browser returns from Google or an email link. */
export function squareClient(url: string, publishableKey: string): Promise<SupabaseClient> {
  let c = clients.get(url)
  if (!c) {
    c = import('@supabase/supabase-js').then((m) => m.createClient(url, publishableKey))
    clients.set(url, c)
  }
  return c
}

/** The square's access token, or null when nobody is signed in to it. */
export async function squareToken(url: string, key: string): Promise<string | null> {
  const { data } = await (await squareClient(url, key)).auth.getSession()
  return data.session?.access_token ?? null
}

/** Email a sign-in link. Only people who already have an account in the square get one; the answer never says which. */
export async function squareEmailLink(url: string, key: string, email: string, returnTo: string): Promise<void> {
  const { error } = await (await squareClient(url, key)).auth.signInWithOtp({ email, options: { emailRedirectTo: returnTo, shouldCreateUser: false } })
  // "Signups not allowed" means: no such person here. Treat it like success so the page cannot be used to find out who is a member.
  if (error && !/signups? not allowed|not found/i.test(error.message)) throw new Error(error.message)
}

export async function squareGoogle(url: string, key: string, returnTo: string): Promise<void> {
  const { error } = await (await squareClient(url, key)).auth.signInWithOAuth({ provider: 'google', options: { redirectTo: returnTo } })
  if (error) throw new Error(error.message)
}

export async function squareSignOut(url: string, key: string): Promise<void> {
  await (await squareClient(url, key)).auth.signOut()
}
