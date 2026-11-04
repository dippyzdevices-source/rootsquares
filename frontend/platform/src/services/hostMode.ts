// Which site is this browser tab showing? The platform (rootsquares.com, localhost) or one square, chosen by the host name (ADR 028):
// <slug>.localhost on a developer machine, <slug>.<square domain> or a custom domain in production. VITE_PLATFORM_HOSTS lists the platform's own
// host names (comma separated); every other host is a square, and the platform API tells which one (GET /public/hosts/<host>).
const LOCAL = ['localhost', '127.0.0.1']
const platformHosts = (((import.meta.env.VITE_PLATFORM_HOSTS as string | undefined) ?? '').split(',').map((h) => h.trim().toLowerCase()).filter(Boolean))
const hosts = platformHosts.length ? platformHosts : LOCAL

export const siteHost = typeof window === 'undefined' ? 'localhost' : window.location.hostname.toLowerCase()
export const isSquareHost = !hosts.includes(siteHost) && !LOCAL.includes(siteHost)

// While developing, the real square site (square/frontend, the BCA app, W6-R29) runs on its own port next to the platform. VITE_SQUARE_APP_PORT sets
// it (default 5274; empty = none, the old hello-world page is shown). With the mock API there is no square app, so the hello-world page stays.
const squareAppPort = import.meta.env.VITE_USE_MOCK === 'true' ? '' : ((import.meta.env.VITE_SQUARE_APP_PORT as string | undefined) ?? (import.meta.env.DEV ? '5274' : ''))

/**
 * The neutral demo site (W10-R14): the square app in demo mode (`?demo=1&theme=<id>`, sample content and images, never any square's data) shown in the theme previews.
 * VITE_DEMO_SITE_URL sets its address (production: e.g. https://demo.rootsquares.com/); while developing it is demo.localhost on the square app's port. '' = none (the sketch is shown).
 */
export const demoSiteUrl: string = (() => {
  const set = (import.meta.env.VITE_DEMO_SITE_URL as string | undefined)?.trim()
  if (set) return set.replace(/\/?$/, '/')
  if (import.meta.env.DEV && squareAppPort && typeof window !== 'undefined' && LOCAL.includes(window.location.hostname)) return `${window.location.protocol}//demo.localhost:${squareAppPort}/`
  return ''
})()
export const liveSitePreview = !!demoSiteUrl

/** Where a square's site lives: the square app's port on <slug>.localhost while developing, its own domain otherwise. */
export function squareSiteUrl(sq: { slug: string; domain: string }): string {
  const l = window.location
  if (LOCAL.includes(l.hostname)) return `${l.protocol}//${sq.slug}.localhost${squareAppPort ? ':' + squareAppPort : l.port ? ':' + l.port : ''}/`
  return `https://${sq.domain}/`
}

/** On a square's host name on the platform's own dev server (<slug>.localhost:5273) the visitor belongs on the square app: its address, or null. */
export function squareAppRedirect(): string | null {
  const l = window.location
  if (!squareAppPort || !isSquareHost || !l.hostname.endsWith('.localhost') || l.port === squareAppPort) return null
  return `${l.protocol}//${l.hostname}:${squareAppPort}${l.pathname}${l.search}${l.hash}`
}
