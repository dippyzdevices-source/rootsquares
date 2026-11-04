import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { landing, type Role } from '@/auth/roles'
import { forgetProviderToken, getProvider, providerEnabled } from '@/services/authProvider'
import { ApiError, platform, type PlatformUser, type SignupInput } from '@/services/platform'

// Two ways in (ADR 028): the platform's own cookie login (when no identity provider is set) and the identity provider (Supabase/Neon JWT, when
// VITE_AUTH_PROVIDER is set). Staff of rootsquares sign in to their own application, never here (ADR 083). Either way this store holds the user returned by /auth/me. Everybody here is the owner of their
// own squares (squareOwner). The customer app has no console of its own since W23-R82 (a square's admin is the square app's own /admin).
export const useAuthStore = defineStore('auth', () => {
  const user = ref<PlatformUser | null>(null)
  const loaded = ref(false)
  let pending: Promise<void> | null = null
  // The first /auth/me (asked by the router guard when the page opens) can still be in flight when the person signs in, and its late 'nobody' answer must not
  // overwrite the user that sign-in just set (the page would then stay on the sign-in form). Every explicit change of user bumps this.
  let epoch = 0
  const setUser = (u: PlatformUser | null) => { epoch++; user.value = u; loaded.value = true }

  const role = computed<Role | null>(() => (user.value ? 'squareOwner' : null))
  /** Signed in through the provider but no organisation yet: onboarding comes before the dashboard. */
  const needsOrg = computed(() => !!user.value && user.value.organizations.length === 0)
  const landingPath = computed(() => (role.value ? landing(role.value) : '/login'))

  /** /auth/me, asking again a few times when the server could not be reached at all (status 0: a refused or dropped connection, seen right after the
   * Google redirect, W13-R7). Only a real answer counts: an unreachable server is not 'nobody is signed in', and must not send the page to /login. */
  async function askWhoAmI(): Promise<PlatformUser> {
    for (let attempt = 0; ; attempt++) {
      try { return await platform.me() } catch (e) {
        if (!(e instanceof ApiError && e.status === 0) || attempt >= 3) throw e
        await new Promise((resolve) => setTimeout(resolve, 300 * (attempt + 1)))
      }
    }
  }

  /** Ask the server who is signed in (once). Router guards wait for it. */
  function load(): Promise<void> {
    if (loaded.value) return Promise.resolve()
    const seen = epoch
    pending ??= askWhoAmI().then((u) => { if (seen === epoch) user.value = u }, () => { if (seen === epoch) user.value = null }).finally(() => { loaded.value = true })
    return pending
  }
  async function signOutProvider() {
    forgetProviderToken()
    if (!providerEnabled) return
    try { await (await getProvider()).signOut() } catch { /* nothing to sign out of */ }
  }
  async function signup(input: SignupInput) { setUser(await platform.signup(input)) }
  async function login(email: string, password: string) {
    await signOutProvider() // an explicit Authorization header wins over the cookie, so a leftover provider session must go first
    setUser(await platform.login(email, password))
  }
  async function logout() {
    try { await platform.logout() } finally { await signOutProvider(); setUser(null) }
  }

  // Provider sign-in. The organisation name typed at sign-up survives the email verification step in localStorage (not sensitive).
  const PENDING_ORG = 'rs-pending-org'
  const pendingOrg = (): string => { try { return localStorage.getItem(PENDING_ORG) ?? '' } catch { return '' } }
  const setPendingOrg = (v: string) => { try { v ? localStorage.setItem(PENDING_ORG, v) : localStorage.removeItem(PENDING_ORG) } catch { /* storage unavailable */ } }

  async function afterProviderSignIn(orgName?: string) {
    forgetProviderToken()
    let u = await platform.me() // creates the platform user on first sight
    const wanted = (orgName ?? pendingOrg()).trim()
    if (u.organizations.length === 0 && wanted) u = await platform.createOrganization(wanted)
    setPendingOrg('')
    setUser(u)
  }
  /** 'verify' = the provider sent a verification email first; sign in after confirming it. */
  async function providerSignup(input: SignupInput): Promise<'signedIn' | 'verify'> {
    const { signedIn } = await (await getProvider()).signUp({ email: input.email, password: input.password, name: input.name })
    if (!signedIn) { setPendingOrg(input.organization_name.trim()); return 'verify' }
    await afterProviderSignIn(input.organization_name)
    return 'signedIn'
  }
  async function providerLogin(email: string, password: string) {
    await (await getProvider()).signIn(email, password)
    await afterProviderSignIn()
  }
  const resetRedirect = () => `${window.location.origin}/reset-password`
  async function providerRequestPasswordReset(email: string) { await (await getProvider()).requestPasswordReset(email, resetRedirect()) }
  async function providerHasRecoverySession(): Promise<boolean> { return providerEnabled && (await (await getProvider()).hasRecoverySession()) }
  async function providerUpdatePassword(password: string) {
    await (await getProvider()).updatePassword(password)
    await afterProviderSignIn() // a reset also signs the person in
  }
  /** Hands over to Google; the page returns to /dashboard signed in (Supabase: redirect URL must be allowed in its dashboard). */
  async function providerGoogle() {
    await signOutProvider() // never carry a previous provider session into a new Google sign-in
    await (await getProvider()).signInWithGoogle(`${window.location.origin}/dashboard`)
  }
  /** Deletes the account; returns false when the sign-in account at the identity provider remains. */
  async function deleteAccount(confirmEmail: string): Promise<boolean> {
    const removed = await platform.deleteAccount(confirmEmail)
    await signOutProvider() // the provider session would otherwise create a fresh, empty account on the next request
    setUser(null)
    return removed
  }
  async function createOrganization(name: string) { setUser(await platform.createOrganization(name.trim())) }
  return { user, loaded, role, needsOrg, landingPath, load, signup, login, logout, providerSignup, providerLogin, providerGoogle, providerRequestPasswordReset, providerHasRecoverySession, providerUpdatePassword, deleteAccount, createOrganization }
})
