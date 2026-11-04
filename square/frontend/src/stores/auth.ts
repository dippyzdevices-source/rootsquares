import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { MiniSession } from '../services/neonAuthAdapter'
import { supabase } from '../services/supabaseClient'
import { setSupportMode, type SupportInfo } from '../services/supportSession'

export interface LocalUser {
  id: number
  email: string
  phone: string | null
  role: string
  support?: SupportInfo // only in a rootsquares support session (ADR 089)
}

export const useAuthStore = defineStore('auth', () => {
  const session = ref<MiniSession | null>(null)
  const user = ref<LocalUser | null>(null)
  const loading = ref(true)

  const isAuthenticated = computed(() => session.value !== null)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isVolunteer = computed(() => user.value?.role === 'volunteer')

  // Google (and any future OAuth provider) puts profile info on Supabase's own
  // user_metadata — no backend column or round-trip needed to show it. Both are null for a
  // plain email/password account, so every consumer must handle the no-avatar/no-name case.
  const avatarUrl = computed<string | null>(() => {
    const metadata = session.value?.user?.user_metadata as Record<string, unknown> | undefined
    return (metadata?.avatar_url as string) ?? (metadata?.picture as string) ?? null
  })
  const displayName = computed<string | null>(() => {
    const metadata = session.value?.user?.user_metadata as Record<string, unknown> | undefined
    return (metadata?.full_name as string) ?? (metadata?.name as string) ?? null
  })

  // Memoized so the router guard can safely `await initialize()` on every navigation —
  // Vue Router's initial navigation can start resolving before main.ts's own
  // `initialize()` call finishes (or even before app.mount() runs at all), which was
  // racing a hard-reload of a protected route straight to /login. Awaiting this from
  // the guard itself (see router/index.ts) makes every navigation, first or not, wait
  // for the real auth state before deciding anything.
  let initPromise: Promise<void> | null = null

  async function fetchLocalUser() {
    if (!session.value) {
      user.value = null
      return
    }
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL as string
    const response = await fetch(`${apiBaseUrl}/api/auth/me`, {
      headers: { Authorization: `Bearer ${session.value.access_token}` },
    })
    user.value = response.ok ? ((await response.json()) as LocalUser) : null
    setSupportMode(user.value?.support ?? null)
  }

  function initialize(): Promise<void> {
    if (!initPromise) {
      initPromise = (async () => {
        loading.value = true
        const { data } = await supabase.auth.getSession()
        session.value = data.session
        await fetchLocalUser()
        supabase.auth.onAuthStateChange((_event, newSession) => {
          session.value = newSession
          fetchLocalUser()
        })
        loading.value = false
      })()
    }
    return initPromise
  }

  async function signUp(email: string, password: string, phone?: string) {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: phone ? { data: { phone } } : undefined,
    })
    if (error) throw error
  }

  // Neon Auth (local/test) confirms a new account with a 6-digit emailed code. Returns whether
  // a session exists afterwards — Neon's docs don't say if verifying also signs the user in, so
  // ask instead of assuming (RegisterView then routes to the dashboard or to /login).
  async function verifyEmailCode(email: string, code: string): Promise<boolean> {
    const { error } = await supabase.auth.verifyOtp({ email, token: code, type: 'signup' })
    if (error) throw error
    const { data } = await supabase.auth.getSession()
    session.value = data.session
    try {
      await fetchLocalUser()
    } catch {
      // Verification already succeeded (the code is consumed) — a failed profile load must not
      // read as a failed verification. The profile is refetched on the next auth-state change.
    }
    return data.session !== null
  }

  async function resendVerificationCode(email: string) {
    const { error } = await supabase.auth.resend({ type: 'signup', email })
    if (error) throw error
  }

  async function signInWithPassword(email: string, password: string) {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  async function signInWithGoogle() {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
    if (error) throw error
  }

  async function signOut() {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
    session.value = null
    user.value = null
  }

  async function requestPasswordReset(email: string) {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    })
    if (error) throw error
  }

  async function updatePassword(password: string) {
    const { error } = await supabase.auth.updateUser({ password })
    if (error) throw error
  }

  return {
    session,
    user,
    loading,
    isAuthenticated,
    isAdmin,
    isVolunteer,
    avatarUrl,
    displayName,
    initialize,
    signUp,
    verifyEmailCode,
    resendVerificationCode,
    signInWithPassword,
    signInWithGoogle,
    signOut,
    requestPasswordReset,
    updatePassword,
  }
})
