import type { LocationQuery, RouteLocationRaw } from 'vue-router'

// What a visitor chose before signing up (W12-R21): the launch package or the Event pass from Pricing (?package= / ?running=event), a theme from Templates
// (?theme=). The choice rides along Sign up and Sign in and lands on Create square, which reads it. (Sign-in with Google comes back to the dashboard and loses it.)
const KEYS = ['package', 'running', 'theme'] as const

export function startQuery(query: LocationQuery): Record<string, string> {
  const out: Record<string, string> = {}
  for (const k of KEYS) {
    const v = query[k]
    if (typeof v === 'string' && v) out[k] = v
  }
  return out
}

/** Signed in: straight to Create square with the choice. Not signed in: Sign up first, carrying the choice. */
export function startTarget(signedIn: boolean, query: Record<string, string>): RouteLocationRaw {
  return { path: signedIn ? '/squares/new' : '/signup', query }
}
