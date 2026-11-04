// The visit beacon of the public site (rootsquares ADR 090, W23-R78).
//
// After a page change the site tells its own server which page was shown and where the visitor came from, so the owner can see how the site is used. It is built so
// that nothing about the visitor is kept: no cookie, nothing in the browser's storage, no identifier, only the page path and the referring page. The server decides
// whether anything is counted (the owner must have switched counting on); the site sends nothing at all unless the square says counting is on, never in the admin area,
// never for a signed-in admin, never in a support session or the demo, and never when the visitor has asked not to be tracked (Do Not Track, Global Privacy Control).

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
const EXCLUDED = ['/admin', '/api', '/login', '/register', '/auth', '/support', '/theme-review']

let lastPath = ''
let firstView = true

/** Has the visitor asked not to be tracked? Both signals count; either one means nothing is sent. */
export function trackingRefused(nav: Navigator = navigator): boolean {
  const n = nav as Navigator & { globalPrivacyControl?: boolean; msDoNotTrack?: string }
  return nav.doNotTrack === '1' || n.msDoNotTrack === '1' || n.globalPrivacyControl === true
}

/** The page path as it is counted: no query, no fragment; null for a page that is not part of the public site. */
export function countedPath(path: string): string | null {
  const clean = path.split('?')[0]!.split('#')[0]!
  const low = clean.toLowerCase()
  return EXCLUDED.some((p) => low === p || low.startsWith(p + '/')) ? null : clean || '/'
}

export interface BeaconContext {
  enabled: boolean
  isAdmin: boolean
  inSupportSession: boolean
  demo: boolean
}

/** Tell the server a page was shown. `from` is the page the visitor came from inside the site (empty for the first page: the browser's own referrer is used). */
export function sendPageView(path: string, from: string, ctx: BeaconContext, win: Window = window): boolean {
  if (!ctx.enabled || ctx.isAdmin || ctx.inSupportSession || ctx.demo) return false
  if (trackingRefused(win.navigator)) return false
  const counted = countedPath(path)
  if (counted === null || counted === lastPath) return false
  lastPath = counted
  const referrer = firstView ? win.document.referrer : from ? win.location.origin + from : ''
  firstView = false
  const body = JSON.stringify({ path: counted, referrer })
  const url = `${API_BASE_URL}/api/analytics/hit`
  try {
    if (win.navigator.sendBeacon?.(url, new Blob([body], { type: 'text/plain' }))) return true // text/plain: no preflight, the server reads it as JSON
    void win.fetch(url, { method: 'POST', body, keepalive: true, headers: { 'Content-Type': 'text/plain' }, credentials: 'omit' })
    return true
  } catch {
    return false // a counter must never break a page
  }
}

/** For tests. */
export function resetBeacon(): void {
  lastPath = ''
  firstView = true
}
