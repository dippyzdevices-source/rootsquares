// A rootsquares support session in this tab (rootsquares ADR 089, W23-R66).
//
// A staff member opens the square's admin from the admin application at /admin#support=<token>. The token is signed by the platform; it is taken out of the
// address at once (so it is never kept in the history or sent anywhere by a link), kept in this tab only (sessionStorage), and used instead of a sign-in.
// The server decides everything (it reads the owner's grant on every request); this file only makes the page honest: it never writes in a read only session
// and says so, and it tells the banner when the access has ended.
import type { MiniAuthClient, MiniSession } from './neonAuthAdapter'

const KEY = 'rs_support_token'
const HASH = '#support='
export const SUPPORT_USER_ID = 'rootsquares-support'

export interface SupportInfo {
  name: string
  scopes: string[]
  allow_changes: boolean
  ends_at: string
}

type Listener = (message: string) => void
const listeners = new Set<Listener>()
let endedMessage = ''

function store(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null // storage blocked: no support session in this tab
  }
}

/** Take a token out of the address (and out of the history) and keep it for this tab. Returns whether one was found. */
export function captureSupportToken(win: Window = window): boolean {
  const hash = win.location.hash
  if (!hash.startsWith(HASH)) return false
  const token = decodeURIComponent(hash.slice(HASH.length)).trim()
  win.history.replaceState(null, '', win.location.pathname + win.location.search)
  if (!token) return false
  store()?.setItem(KEY, token)
  return true
}

export function supportToken(): string | null {
  return store()?.getItem(KEY) ?? null
}

export function inSupportSession(): boolean {
  return supportToken() !== null
}

export function endSupportSession(): void {
  store()?.removeItem(KEY)
}

/** The page tells this when the server says the access is over or a thing is not allowed: the banner shows it. */
export function onSupportMessage(fn: Listener): () => void {
  listeners.add(fn)
  if (endedMessage) fn(endedMessage)
  return () => listeners.delete(fn)
}

function tell(message: string, ended = false): void {
  if (ended) endedMessage = message
  listeners.forEach((fn) => fn(message))
}

/** The sign-in client of the square, or, in a support session, one whose session is the support token (every service file asks `supabase.auth.getSession()`). */
export function withSupport(client: MiniAuthClient): MiniAuthClient {
  if (!inSupportSession()) return client
  const synthetic = (): MiniSession => ({ access_token: supportToken() ?? '', user: { id: SUPPORT_USER_ID, email: 'support@rootsquares.com' } })
  return {
    auth: {
      ...client.auth,
      getSession: async () => ({ data: { session: supportToken() ? synthetic() : null } }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => undefined } } }),
      signOut: async () => {
        endSupportSession()
        return { error: null }
      },
    },
  }
}

const SAFE = new Set(['GET', 'HEAD', 'OPTIONS'])
let readOnly = true // until /api/auth/me says changes are allowed (the safe side)

/** The banner and the page tell the guard what the owner allowed, from the support block of GET /api/auth/me. */
export function setSupportMode(info: SupportInfo | null): void {
  readOnly = !info || !info.allow_changes
  document.documentElement.dataset.support = info ? (info.allow_changes ? 'changes' : 'readonly') : ''
}

/** In a support session: a change is refused here when the session is read only (the server refuses it too), and a refusal from the server is reported. */
export function installSupportFetch(win: Window = window): void {
  if (!inSupportSession()) return
  const original = win.fetch.bind(win)
  win.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
    if (!SAFE.has(method) && readOnly) {
      tell('This support session is read only: nothing was changed.')
      return new Response(JSON.stringify({ error: 'This support session can look but not change anything.', code: 'support_read_only' }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    const response = await original(input, init)
    if (response.status === 403 || response.status === 401) {
      try {
        const body = (await response.clone().json()) as { code?: string; error?: string }
        if (body.code === 'support_ended' || body.code === 'support_invalid') {
          endSupportSession()
          tell('The support access has ended.', true)
        } else if (body.code?.startsWith('support_')) {
          tell(body.error ?? 'Support access does not reach this.')
        }
      } catch {
        /* not our JSON: leave it to the page */
      }
    }
    return response
  }
}

// Runs when the first module imports this file (main.ts imports it first): take the token out of the address before anything else reads the address.
if (typeof window !== 'undefined') {
  captureSupportToken()
  installSupportFetch()
}
