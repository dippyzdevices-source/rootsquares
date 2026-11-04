// Demo mode (W10-R14): `?demo=1` makes this square app show neutral sample data and never call a backend, so the platform can preview any theme
// without a square's own content. Remembered for the browser tab (`?demo=0` clears it). It exposes no data, so it also works in production builds.
// This file must be the first import of main.ts: services/squareConfig.ts asks for the square's configuration with a top-level await, before anything else runs.
import { demoAnswer, demoResponse } from './demoFetch'

const KEY = 'rs-demo'
const THEME_KEY = 'rs-preview-theme'
export const DEMO_AUTH_HOST = 'https://demo.invalid'

/** Is demo mode on for this visit? The test suite is never in demo mode unless a spec installs it directly. */
export function demoActive(search = typeof window === 'undefined' ? '' : window.location.search): boolean {
  if (typeof window === 'undefined' || import.meta.env.MODE === 'test') return false
  const asked = new URLSearchParams(search).get('demo')
  try {
    if (asked === '1') window.sessionStorage.setItem(KEY, '1')
    else if (asked === '0') window.sessionStorage.removeItem(KEY)
    return window.sessionStorage.getItem(KEY) === '1'
  } catch {
    return asked === '1' // storage blocked: this page load only
  }
}

/** The theme the sample square wears: the `?theme=` of this visit, kept for the tab like the development preview (services/squareConfig.ts reads the same key). */
export function demoTheme(search = window.location.search): string {
  const asked = new URLSearchParams(search).get('theme')
  try {
    if (asked === 'default') window.sessionStorage.removeItem(THEME_KEY)
    else if (asked) window.sessionStorage.setItem(THEME_KEY, asked)
    return window.sessionStorage.getItem(THEME_KEY) ?? ''
  } catch {
    return asked && asked !== 'default' ? asked : ''
  }
}

/** Replace `fetch`: calls to the API and to the (never answering) auth host are answered from the fixtures; everything else passes through. Returns the undo. */
export function installDemoFetch(themeId = ''): () => void {
  const real = window.fetch.bind(window)
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const raw = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const url = new URL(raw, window.location.href)
    const method = (init?.method ?? (typeof input === 'object' && 'method' in input ? input.method : 'GET')).toUpperCase()
    if (url.origin === DEMO_AUTH_HOST) return demoResponse({ status: 401, body: { message: 'demo' } })
    if (url.pathname.startsWith('/api/')) return demoResponse(demoAnswer(method, url.pathname, url.searchParams, themeId))
    return real(input, init)
  }
  return () => { window.fetch = real }
}

if (demoActive()) installDemoFetch(demoTheme())
