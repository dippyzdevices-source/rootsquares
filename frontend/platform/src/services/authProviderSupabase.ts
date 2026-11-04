import { createClient } from '@supabase/supabase-js'
import { ProviderError, type ProviderClient } from './authProvider'

export function createSupabaseClient(url: string, publishableKey: string): ProviderClient {
  const sb = createClient(url, publishableKey)
  return {
    async signUp({ email, password, name }) {
      const { data, error } = await sb.auth.signUp({ email, password, options: { data: { full_name: name } } })
      if (error) throw new ProviderError(error.message)
      return { signedIn: !!data.session }
    },
    async signIn(email, password) {
      const { error } = await sb.auth.signInWithPassword({ email, password })
      if (error) throw new ProviderError(error.message)
    },
    async signInWithGoogle(redirectTo) {
      const { error } = await sb.auth.signInWithOAuth({ provider: 'google', options: { redirectTo } })
      if (error) throw new ProviderError(error.message)
    },
    async requestPasswordReset(email, redirectTo) {
      const { error } = await sb.auth.resetPasswordForEmail(email, { redirectTo })
      if (error) throw new ProviderError(error.message)
    },
    async hasRecoverySession() {
      // getSession waits for the client to read the recovery session out of the address, so this is the right moment to ask
      return (await sb.auth.getSession()).data.session !== null
    },
    async updatePassword(newPassword) {
      const { error } = await sb.auth.updateUser({ password: newPassword })
      if (error) throw new ProviderError(error.message)
    },
    async signOut() {
      await sb.auth.signOut()
    },
    async accessToken() {
      const { data } = await sb.auth.getSession()
      return data.session?.access_token ?? null
    },
  }
}
