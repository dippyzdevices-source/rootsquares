// Role model and route guard of the customer app. Pure module (no aliases, no framework imports) so node tests can import it.
// Real accounts only produce one role: squareOwner (the staff of rootsquares have their own application, ADR 083). Since W23-R82 the customer app has no console of its
// own (the clickable prototype with its finer roles, sections and demo data was removed): a square's real admin is the square app's own `/admin`.

export type Role = 'squareOwner'

export const ROLES: readonly Role[] = ['squareOwner']
export const isRole = (v: unknown): v is Role => typeof v === 'string' && (ROLES as readonly string[]).includes(v)

/** Where a signed-in user lands: on their dashboard of squares. */
export function landing(_role: Role): string {
  return '/dashboard'
}

export interface AuthState { role: Role | null; square: string | null; needsOrg?: boolean }

const under = (path: string, base: string) => path === base || path.startsWith(base + '/')

/** Route guard: returns the path to redirect to, or null to allow. */
export function guardRedirect(s: AuthState, path: string): string | null {
  // signed-in users do not need the sign-in and sign-up pages
  if (s.role && (path === '/login' || path === '/signup')) return landing(s.role)
  const platformPage = under(path, '/dashboard') || under(path, '/squares') || under(path, '/account')
  // a user who signed in through the identity provider and has no organisation yet goes through onboarding first
  if (path === '/organization/new') return !s.role ? '/login' : s.needsOrg ? null : landing(s.role)
  if (s.role && s.needsOrg && platformPage) return '/organization/new'
  if (!platformPage) return null
  return s.role ? null : '/login'
}
