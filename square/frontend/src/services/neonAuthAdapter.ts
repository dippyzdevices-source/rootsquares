import { createAuthClient } from '@neondatabase/auth'

export interface MiniSession {
  access_token: string
  user: {
    id: string
    email?: string
    user_metadata?: Record<string, unknown>
  }
}

export interface MiniAuthClient {
  auth: {
    getSession(): Promise<{ data: { session: MiniSession | null } }>
    onAuthStateChange(
      callback: (event: string, session: MiniSession | null) => void,
    ): { data: { subscription: { unsubscribe: () => void } } }
    signUp(args: {
      email: string
      password: string
      options?: { data?: Record<string, unknown> }
    }): Promise<{ error: Error | null }>
    signInWithPassword(args: { email: string; password: string }): Promise<{ error: Error | null }>
    signInWithOAuth(args: {
      provider: string
      options?: { redirectTo?: string }
    }): Promise<{ error: Error | null }>
    signOut(): Promise<{ error: Error | null }>
    resetPasswordForEmail(email: string, options?: { redirectTo?: string }): Promise<{ error: Error | null }>
    updateUser(args: { password: string }): Promise<{ error: Error | null }>
    verifyOtp(args: { email: string; token: string; type: 'signup' }): Promise<{ error: Error | null }>
    resend(args: { type: 'signup'; email: string }): Promise<{ error: Error | null }>
  }
}

interface NeonSessionUser {
  id: string
  email?: string
  name?: string | null
  image?: string | null
}

interface NeonSessionData {
  user: NeonSessionUser
}

export function normalizeNeonSession(
  data: NeonSessionData | null,
  accessToken: string,
): MiniSession | null {
  if (!data) return null
  return {
    access_token: accessToken,
    user: {
      id: data.user.id,
      email: data.user.email,
      user_metadata: {
        avatar_url: data.user.image ?? undefined,
        picture: data.user.image ?? undefined,
        full_name: data.user.name ?? undefined,
        name: data.user.name ?? undefined,
      },
    },
  }
}

export function createNeonAuthAdapter(neonAuthUrl: string): MiniAuthClient {
  // `createAuthClient(url)` defaults to Neon's BetterAuthVanillaAdapter, which returns the
  // real Better Auth client (`signIn.email`, `signUp.email`, `signIn.social`, `signOut`,
  // `getSession`, `useSession`, `requestPasswordReset`, `resetPassword`, ...) verbatim --
  // see the task-6 report for how this was confirmed against the installed package's
  // actual source/types (not just its public docs).
  const client = createAuthClient(neonAuthUrl)

  async function currentSession(): Promise<MiniSession | null> {
    const { data } = await client.getSession()
    if (!data) return null
    // There is no `client.token()` method -- `jwtClient()` (bundled unconditionally by
    // @neondatabase/auth's NeonAuthAdapterCore, regardless of what plugins are passed to
    // BetterAuthVanillaAdapter/createAuthClient) only exposes `.jwks()`. The real bearer JWT
    // instead arrives as a `set-auth-jwt` response header on every successful auth call and
    // is injected client-side onto `data.session.token` by @neondatabase/auth's own
    // `onSuccess` fetch hook (see NeonAuthAdapterCore.getJWTToken(), which itself just reads
    // `session.data.session.token` off a getSession() call -- the same thing done here).
    return normalizeNeonSession(data, data.session?.token ?? '')
  }

  return {
    auth: {
      async getSession() {
        return { data: { session: await currentSession() } }
      },
      onAuthStateChange(callback) {
        // `useSession` is a nanostores atom; `.subscribe()` (unlike `.listen()`) calls the
        // listener immediately with the current value in addition to on every change, and
        // returns a plain unsubscribe function directly (not `{ unsubscribe }`).
        const unsubscribe = client.useSession.subscribe(() => {
          void currentSession().then((session) => callback('CHANGE', session))
        })
        return { data: { subscription: { unsubscribe } } }
      },
      async signUp({ email, password }) {
        // Better Auth's signUp.email requires `name` (Supabase's doesn't collect one at
        // registration) -- derive a placeholder from the email's local-part. User.phone
        // is serialized but never actually set from signup metadata on the Supabase path
        // either (see backend/app/auth/routes.py), so there's no functional parity gap here.
        const name = email.split('@')[0]
        const { error } = await client.signUp.email({ email, password, name })
        return { error: error ? new Error(error.message) : null }
      },
      async signInWithPassword({ email, password }) {
        const { error } = await client.signIn.email({ email, password })
        return { error: error ? new Error(error.message) : null }
      },
      async signInWithOAuth({ provider, options }) {
        // Better Auth's `provider` param is a closed enum of known social provider ids
        // (e.g. "google"), not an arbitrary string -- our own MiniAuthClient interface keeps
        // it a plain `string` to mirror Supabase's own broader `Provider` union, since this
        // app only ever passes `'google'` through it in practice.
        const { error } = await client.signIn.social({
          provider: provider as Parameters<typeof client.signIn.social>[0]['provider'],
          callbackURL: options?.redirectTo,
        })
        return { error: error ? new Error(error.message) : null }
      },
      async signOut() {
        const { error } = await client.signOut()
        return { error: error ? new Error(error.message) : null }
      },
      async resetPasswordForEmail(email, options) {
        const { error } = await client.requestPasswordReset({
          email,
          redirectTo: options?.redirectTo,
        })
        return { error: error ? new Error(error.message) : null }
      },
      async updateUser({ password }) {
        // The emailed reset link lands on ResetPasswordView.vue with ?token=... in the URL
        // (Better Auth's own flow, via its /reset-password/:token redirect callback, unlike
        // Supabase's implicit recovery session) -- read it here so the page component itself
        // needs no change for either provider.
        const token = new URLSearchParams(window.location.search).get('token')
        const { error } = await client.resetPassword({ newPassword: password, token: token ?? '' })
        return { error: error ? new Error(error.message) : null }
      },
      async verifyOtp({ email, token }) {
        // Same signature as supabase-js's auth.verifyOtp so callers never branch on provider;
        // Better Auth's emailOtp plugin (bundled by @neondatabase/auth) calls the code `otp`.
        const { error } = await client.emailOtp.verifyEmail({ email, otp: token })
        return { error: error ? new Error(error.message) : null }
      },
      async resend({ email }) {
        const { error } = await client.emailOtp.sendVerificationOtp({ email, type: 'email-verification' })
        return { error: error ? new Error(error.message) : null }
      },
    },
  }
}
