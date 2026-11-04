// Answers the square app's API calls from the demo fixtures (W10-R14). Pure: a method and a URL in, a status and a JSON body out, so it can be tested
// without a browser. Reads only (GET); anything that would change data is refused with a plain sentence the forms already show.
import {
  ALBUMS, ALBUM_DETAILS, COMMITTEE, COVERAGE, EVENTS, EVENT_DETAILS, FOUNDERS, GALLERY_MEDIA, LOOKUPS, MAGAZINES, MEMBERSHIP_TYPES, NEWS, NEWS_ARTICLES,
  SETTINGS, SPONSORS, TESTIMONIALS, TICKET_TYPES, demoConfig,
} from './fixtures'

export interface DemoAnswer {
  status: number
  body: unknown
}

const ok = (body: unknown): DemoAnswer => ({ status: 200, body })
const notFound = (): DemoAnswer => ({ status: 404, body: { detail: 'demo' } })
const REFUSED = 'This is a demo; nothing is saved.'

function page<T>(items: T[], params: URLSearchParams, fallbackPerPage: number) {
  const perPage = Math.max(1, Number(params.get('per_page')) || fallbackPerPage)
  const current = Math.max(1, Number(params.get('page')) || 1)
  const totalPages = Math.max(1, Math.ceil(items.length / perPage))
  return { items: items.slice((current - 1) * perPage, current * perPage), page: current, per_page: perPage, total: items.length, total_pages: totalPages }
}

/** `themeId` is the theme the sample square wears (the `?theme=` of the visit). */
export function demoAnswer(method: string, path: string, params: URLSearchParams, themeId = ''): DemoAnswer {
  if (path === '/api/square/config') return ok(demoConfig(themeId))
  if (method !== 'GET') return { status: 403, body: { detail: REFUSED, error: REFUSED } }

  if (path === '/api/settings') return ok(SETTINGS)
  const lookup = /^\/api\/lookups\/([a-z_]+)$/.exec(path)
  if (lookup) return ok({ items: LOOKUPS[lookup[1]!] ?? [] })

  if (path === '/api/events') {
    const past = params.get('when') === 'past'
    const type = params.get('type')
    const now = Date.now()
    const list = EVENTS.filter((e) => (past ? Date.parse(e.start_datetime) < now : Date.parse(e.start_datetime) >= now) && (!type || e.event_type === type))
    list.sort((a, b) => (past ? -1 : 1) * (Date.parse(a.start_datetime) - Date.parse(b.start_datetime)))
    return ok(page(list, params, 12))
  }
  const eventQr = /^\/api\/events\/([^/]+)\/qr$/.exec(path)
  if (eventQr) return EVENT_DETAILS.some((e) => e.slug === decodeURIComponent(eventQr[1]!)) ? ok({ url: '', qr: '' }) : notFound()
  const event = /^\/api\/events\/([^/]+)$/.exec(path)
  if (event) {
    const found = EVENT_DETAILS.find((e) => e.slug === decodeURIComponent(event[1]!))
    return found ? ok(found) : notFound()
  }
  if (path === '/api/tickets/types') return ok({ items: TICKET_TYPES[Number(params.get('event_id'))] ?? [] })

  if (path === '/api/gallery/albums') {
    const eventId = Number(params.get('event_id')) || 0
    const category = params.get('category')
    const list = ALBUMS.filter((a) => (!category || a.category === category) && (!eventId || ALBUM_DETAILS.find((d) => d.id === a.id)?.event_id === eventId))
    return ok(page(list, params, 20))
  }
  if (path === '/api/gallery/coverage') return ok({ items: COVERAGE })
  if (path === '/api/gallery/media') return ok({ items: GALLERY_MEDIA.slice(0, Math.max(1, Number(params.get('limit')) || 40)) })
  const album = /^\/api\/gallery\/albums\/(\d+)$/.exec(path)
  if (album) {
    const found = ALBUM_DETAILS.find((a) => a.id === Number(album[1]))
    return found ? ok(found) : notFound()
  }

  if (path === '/api/news') {
    const category = params.get('category')
    return ok(page(NEWS.filter((n) => !category || n.category === category), params, 10))
  }
  const article = /^\/api\/news\/([^/]+)$/.exec(path)
  if (article) {
    const found = NEWS_ARTICLES.find((n) => n.slug === decodeURIComponent(article[1]!))
    return found ? ok(found) : notFound()
  }

  if (path === '/api/committee') return ok({ items: COMMITTEE })
  if (path === '/api/founders') return ok({ items: FOUNDERS })
  if (path === '/api/sponsors') return ok({ items: SPONSORS })
  if (path === '/api/testimonials') return ok({ items: TESTIMONIALS })
  if (path === '/api/magazines') return ok({ items: MAGAZINES })
  const magazine = /^\/api\/magazines\/([^/]+)$/.exec(path)
  if (magazine) {
    const found = MAGAZINES.find((m) => m.slug === decodeURIComponent(magazine[1]!))
    return found ? ok(found) : notFound()
  }
  if (path === '/api/memberships/types') return ok({ items: MEMBERSHIP_TYPES })

  // The visitor is always signed out: no profile, no orders, no admin data.
  if (['/api/auth/', '/api/members/', '/api/memberships/', '/api/orders/', '/api/admin/'].some((p) => path.startsWith(p))) {
    return { status: 401, body: { detail: 'demo' } }
  }
  return notFound()
}

/** A fetch Response for an answer. */
export function demoResponse(answer: DemoAnswer): Response {
  return new Response(JSON.stringify(answer.body), { status: answer.status, headers: { 'Content-Type': 'application/json' } })
}
