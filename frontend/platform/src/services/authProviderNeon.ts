import { createAuthClient } from '@neondatabase/auth'
import { ProviderError, type ProviderClient } from './authProvider'

// Neon Auth is a managed Better Auth. There is no client.token(): the bearer JWT arrives on data.session.token of a getSession() call
// (found by the bca-oslo reference against the installed package, see its neonAuthAdapter.ts).
export function createNeonClient(neonAuthUrl: string): ProviderClient {
  const client = createAuthClient(neonAuthUrl)
  const fail = (error: { message?: string } | null | undefined) => {
    if (error) throw new ProviderError(error.message ?? 'Sign-in failed')
  }
  const token = async () => (await client.getSession()).data?.session?.token ?? null
  return {
    async signUp({ email, password, name }) {
      fail((await client.signUp.email({ email, password, name: name || email.split('@')[0]! })).error)
      return { signedIn: (await token()) !== null }
    },
    async signIn(email, password) {
      fail((await client.signIn.email({ email, password })).error)
    },
    async signInWithGoogle(redirectTo) {
      fail((await client.signIn.social({ provider: 'google', callbackURL: redirectTo })).error)
    },
    async requestPasswordReset(email, redirectTo) {
      fail((await client.requestPasswordReset({ email, redirectTo })).error)
    },
    async hasRecoverySession() {
      return new URLSearchParams(window.location.search).get('token') !== null // Better Auth puts the reset token in the link
    },
    async updatePassword(newPassword) {
      const resetToken = new URLSearchParams(window.location.search).get('token') ?? ''
      fail((await client.resetPassword({ newPassword, token: resetToken })).error)
    },
    async signOut() {
      await client.signOut()
    },
    accessToken: token,
  }
}
