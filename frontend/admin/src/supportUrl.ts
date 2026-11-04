// Where a square's own admin is, and how a support session gets there (ADR 089, W23-R68).
// The token goes in the address FRAGMENT (`#support=`): a fragment is never sent to a server or kept in a log, and the square page takes it out of the address at once
// (square/frontend/src/services/supportSession.ts). Never put it in a query string.
const LOCAL = ['localhost', '127.0.0.1']
const squareAppPort = import.meta.env.DEV ? '5274' : '' // the square app's development port (the admin application reads only one environment name, ADR 084)

/** The square's admin: <slug>.localhost on the square app's port while developing, its own domain otherwise. */
export function squareAdminUrl(sq: { slug?: string; domain: string }): string {
  const l = window.location
  if (LOCAL.includes(l.hostname) && sq.slug) return `${l.protocol}//${sq.slug}.localhost${squareAppPort ? ':' + squareAppPort : ''}/admin`
  return `https://${sq.domain}/admin`
}

/** The domain of a square is `<slug>.<suffix>`; the staff API gives the domain, so the slug is its first label. */
export function slugOf(domain: string): string {
  return domain.split('.')[0] ?? domain
}

export function supportLink(sq: { domain: string; slug?: string }, token: string): string {
  return `${squareAdminUrl({ domain: sq.domain, slug: sq.slug ?? slugOf(sq.domain) })}#support=${encodeURIComponent(token)}`
}
