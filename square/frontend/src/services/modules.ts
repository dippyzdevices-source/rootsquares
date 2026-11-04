// The optional modules of this square (rootsquares W8-R9, docs/reference/optional-modules.md; not in bca-oslo).
// The owner chooses them on the platform; the server tells the browser in GET /api/square/config. A module that is off has no menu item, no link,
// no page (the router shows the not-found page) and no API (the server answers 404). Without an answer (single-tenant server, tests) every module is on.
import { squareProfile } from './squareConfig'

export type ModuleKey =
  | 'events'
  | 'payments'
  | 'tickets'
  | 'coupons'
  | 'checkin'
  | 'members'
  | 'memberships'
  | 'volunteering'
  | 'accounting'
  | 'gallery'
  | 'news'
  | 'magazines'
  | 'newsletter'
  | 'testimonials'
  | 'sponsors'
  | 'committee'
  | 'founders'
  | 'donations'
  | 'messages'
  // The always-on parts, which only a custom package can leave out (W19-R24); keys equal the platform's CORE_KEYS
  | 'home'
  | 'about'
  | 'contact'
  | 'legal'
  | 'login'
  | 'account'
  | 'admin'
  | 'settings'
  | 'media'

// Same keys, same order as the backend (square/backend/app/modules.py).
export const MODULE_KEYS: ModuleKey[] = ['events', 'payments', 'tickets', 'coupons', 'checkin', 'members', 'memberships', 'volunteering', 'accounting', 'gallery', 'news', 'magazines', 'newsletter', 'testimonials', 'sponsors', 'committee', 'founders', 'donations', 'messages']

const CORE_KEYS: string[] = ['home', 'about', 'contact', 'legal', 'login', 'account', 'admin', 'settings', 'media']

export function moduleEnabled(key: ModuleKey | undefined): boolean {
  if (key === undefined) return true
  return CORE_KEYS.includes(key) ? !(squareProfile.coreOff ?? []).includes(key) : squareProfile.modules.includes(key)
}

// Path prefix -> module. The first match wins, so the more specific prefix comes first. A path matches a prefix when it equals it or continues with '/'.
// Anything not listed is core (always on).
const PATH_MODULES: [string, ModuleKey][] = [
  ['/events', 'events'],
  ['/donate', 'donations'],
  ['/messages', 'messages'],
  ['/admin/messages', 'messages'],
  ['/admin/donations', 'donations'],
  ['/news/magazines', 'magazines'],
  ['/news', 'news'],
  ['/gallery', 'gallery'],
  ['/membership', 'memberships'],
  ['/membership-drive', 'memberships'],
  ['/testimonials', 'testimonials'],
  ['/newsletter', 'newsletter'],
  ['/orders', 'tickets'],
  ['/committee', 'committee'],
  ['/checkin', 'checkin'],
  ['/member/membership', 'memberships'],
  ['/member/family', 'memberships'], // a household belongs to a membership; an Event pass has people, not families (W11-R42)
  ['/member/tickets', 'tickets'],
  ['/member/volunteering', 'volunteering'],
  ['/member/payments', 'payments'],
  ['/admin/events', 'events'],
  ['/admin/members/import', 'memberships'], // the Excel import creates memberships (W11-R25, ADR 044)
  ['/admin/members/follow-up', 'memberships'],
  ['/admin/members', 'members'],
  ['/admin/memberships', 'memberships'],
  ['/admin/membership-types', 'memberships'],
  ['/admin/tickets', 'tickets'],
  ['/admin/orders', 'tickets'],
  ['/admin/payments', 'payments'],
  ['/admin/checkin', 'checkin'],
  ['/admin/accounting', 'accounting'],
  ['/admin/gallery', 'gallery'],
  ['/admin/news/magazines', 'magazines'],
  ['/admin/news', 'news'],
  ['/admin/newsletter', 'newsletter'],
  ['/admin/testimonials', 'testimonials'],
  ['/admin/volunteers', 'checkin'], // the page that gives members door check-in access (W8-R22); the volunteer tasks are Volunteering's
  ['/admin/committee', 'committee'],
  ['/admin/content/committee', 'committee'],
  ['/admin/content/founders', 'founders'],
  ['/admin/content/sponsors', 'sponsors'],
  ['/admin/content/payments', 'payments'],
  ['/admin/content/magazines', 'magazines'],
  ['/admin/content/pages/events', 'events'],
  ['/admin/content/pages/gallery', 'gallery'],
  ['/admin/content/pages/news', 'news'],
  ['/admin/content/pages/newsletter', 'newsletter'],
  ['/admin/content/pages/membership', 'memberships'],
  ['/admin/content/pages/committee', 'committee'],
  // The always-on parts (W19-R24): after every module above, so a module's own page keeps its module. Without a match a page is not left out.
  ['/about', 'about'],
  ['/heritage', 'about'],
  ['/admin/content/pages/about', 'about'],
  ['/contact', 'contact'],
  ['/privacy', 'legal'],
  ['/terms-of-sale', 'legal'],
  ['/login', 'login'],
  ['/register', 'login'],
  ['/forgot-password', 'login'],
  ['/reset-password', 'login'],
  ['/admin/content/settings', 'settings'],
  ['/admin/settings', 'settings'],
  ['/member', 'account'],
  ['/admin', 'admin'],
]

/** The module a page belongs to, or undefined for a core page. */
export function moduleForPath(path: string): ModuleKey | undefined {
  if (path === '/') return 'home'
  if (/^\/events\/[^/]+\/tickets/.test(path)) return 'tickets'
  for (const [prefix, key] of PATH_MODULES) {
    if (path === prefix || path.startsWith(`${prefix}/`)) return key
  }
  return undefined
}

/** Is this page available in this square? (core pages always are) */
export function pathAvailable(path: string): boolean {
  return moduleEnabled(moduleForPath(path))
}

/**
 * The enabled modules a visitor would know by name, as a short phrase for text that used to say "events, tickets, membership and news" for every
 * square: 'events, tickets and news'. Empty when none is on (W8-R16).
 */
export function offeredPhrase(): string {
  const words: [ModuleKey, string][] = [['events', 'events'], ['tickets', 'tickets'], ['memberships', 'membership'], ['news', 'news']]
  const on = words.filter(([key]) => moduleEnabled(key)).map(([, word]) => word)
  return on.length > 1 ? `${on.slice(0, -1).join(', ')} and ${on[on.length - 1]}` : (on[0] ?? '')
}
