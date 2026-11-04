// Optional modules: the rules the picker applies in the browser, and the catalogue the in-browser mock serves (VITE_USE_MOCK).
// The real catalogue comes from GET /modules (backend/app/platform/modules.py); the server applies the same rules again.
import type { LaunchPackageId, ModuleInfo, StarterSetInfo } from './platform'

export const MOCK_MODULES: ModuleInfo[] = [
  { key: 'events', label: 'Events', description: 'Public list and pages of events, and the events admin.', tier: 'recommended', needs: [] },
  { key: 'payments', label: 'Payments', description: 'Payment records and online payment (Vipps).', tier: 'recommended', needs: [] },
  { key: 'tickets', label: 'Tickets and orders', description: 'Buying tickets, orders, tickets with QR codes and the order emails.', tier: 'recommended', needs: ['events', 'payments'] },
  { key: 'coupons', label: 'Coupons', description: 'Coupon codes at checkout.', tier: 'recommended', needs: ['tickets'], parent: 'tickets' },
  { key: 'checkin', label: 'Check-in', description: 'Scanning tickets at the door, and the Volunteers page that gives members door access.', tier: 'recommended', needs: ['tickets'], parent: 'tickets' },
  { key: 'members', label: 'Members', description: 'The member list (the people roster), families, duplicates and Excel import. Works on its own; Memberships builds on it.', tier: 'recommended', needs: [] },
  { key: 'memberships', label: 'Memberships', description: 'Membership types, the Become a member page, the sign-up drive and member payments. Needs Members.', tier: 'good_to_have', needs: ['members', 'payments'], parent: 'members' },
  { key: 'volunteering', label: 'Volunteering', description: 'Volunteer tasks at events and the volunteering page for members.', tier: 'good_to_have', needs: ['events', 'members'] },
  { key: 'accounting', label: 'Accounting', description: 'Expenses, receipts and the accounting report of each event, and a general book for costs and income that belong to no event (gifts and membership payments). Works without Events.', tier: 'recommended', needs: [] },
  { key: 'gallery', label: 'Gallery', description: 'Photo albums and the gallery page.', tier: 'recommended', needs: [] },
  { key: 'news', label: 'News', description: 'News articles and the News page.', tier: 'recommended', needs: [] },
  { key: 'magazines', label: 'Magazines', description: 'Magazine issues next to the news.', tier: 'good_to_have', needs: ['news'], parent: 'news', starts_off: true },
  { key: 'newsletter', label: 'Newsletter', description: 'A sign-up form and the subscriber list. Newsletters are written and sent in Messages, so it needs Messages. Works without News (it then has its own sign-up page).', tier: 'good_to_have', needs: ['messages'] },
  { key: 'testimonials', label: 'Testimonials', description: 'Words from members, sent in and approved.', tier: 'good_to_have', needs: [] },
  { key: 'sponsors', label: 'Sponsors', description: 'Sponsor logos on the home page.', tier: 'good_to_have', needs: [] },
  { key: 'committee', label: 'Committee', description: 'The Committee page and its admin.', tier: 'recommended', needs: [] },
  { key: 'founders', label: 'Founders', description: "Founders' quotes on the About page.", tier: 'good_to_have', needs: [] },
  { key: 'donations', label: 'Donations', description: 'A donate page: gifts by Vipps or cash, receipts by e-mail, and a list with export. Needs Payments.', tier: 'good_to_have', needs: ['payments'], parent: 'payments', starts_off: true },
  { key: 'messages', label: 'Messages', description: 'E-mail to groups of members, ticket holders, volunteers or donors, scheduled sending, an opt-out list and automatic reminders.', tier: 'recommended', needs: [] },
]

/** The valid form of a choice: what a chosen module needs is added (Memberships needs Members; Members works alone, ADR 044), in catalogue order. */
export function completeModules(catalogue: ModuleInfo[], chosen: string[]): string[] {
  const on = new Set(chosen.filter((k) => catalogue.some((m) => m.key === k)))
  let grew = true
  while (grew) {
    grew = false
    for (const m of catalogue) {
      if (on.has(m.key)) for (const need of m.needs) if (!on.has(need)) { on.add(need); grew = true }
    }
  }
  return catalogue.map((m) => m.key).filter((k) => on.has(k))
}

/** Turning one module off also turns off every module that needs it (turning Members off turns Memberships off, not the other way round). */
export function withoutModule(catalogue: ModuleInfo[], chosen: string[], key: string): string[] {
  const off = new Set([key])
  let grew = true
  while (grew) {
    grew = false
    for (const m of catalogue) if (!off.has(m.key) && m.needs.some((n) => off.has(n))) { off.add(m.key); grew = true }
  }
  return chosen.filter((k) => !off.has(k))
}

/** Switching a module on: what it needs comes on, and so do its sub-switches (the ones the package allows); the owner can turn a sub-switch off again (W14-R13). */
export function withModule(catalogue: ModuleInfo[], chosen: string[], key: string, allowed?: string[]): string[] {
  const kids = catalogue.filter((m) => m.parent === key && !m.starts_off && (!allowed || allowed.includes(m.key))).map((m) => m.key)
  return completeModules(catalogue, [...chosen, key, ...kids])
}

export function recommendedModules(catalogue: ModuleInfo[]): string[] {
  return completeModules(catalogue, catalogue.filter((m) => m.tier === 'recommended').map((m) => m.key))
}

// What a single event needs (ADR 044): no gallery, no memberships; Volunteering brings the people list (Members).
const EVENT_MODULES = ['events', 'payments', 'tickets', 'coupons', 'checkin', 'members', 'volunteering', 'accounting', 'sponsors', 'messages']
// What the Square package includes (backend/app/platform/plans.py SQUARE_MODULES, docs/reference/packages-and-features.md); Grove is everything.
const SQUARE_MODULES = ['events', 'payments', 'tickets', 'members', 'memberships', 'accounting', 'gallery', 'committee', 'messages']
/** The optional modules a launch package lets the owner switch on (the server applies the same rule, backend/app/platform/plans.py). */
export function allowedModules(catalogue: ModuleInfo[], pkg: LaunchPackageId): string[] {
  if (pkg === 'roots') return []
  if (pkg === 'square') return catalogue.filter((m) => SQUARE_MODULES.includes(m.key)).map((m) => m.key)
  if (pkg === 'event') return completeModules(catalogue, EVENT_MODULES)
  return catalogue.map((m) => m.key)
}

/** Modules in display order: the top-level ones in catalogue order, each followed by its sub-switches that are in the same list. */
export function arrangeModules(catalogue: ModuleInfo[], keys: string[]): ModuleInfo[] {
  const mine = catalogue.filter((m) => keys.includes(m.key))
  return mine.filter((m) => !m.parent || !mine.some((p) => p.key === m.parent)).flatMap((m) => [m, ...mine.filter((k) => k.parent === m.key)])
}

/** View 3, 'Recommended' (W15-R27): the kind of group's list is Recommended, every other module is Good to have. The core is shown apart. */
export function recommendationGroups(catalogue: ModuleInfo[], recommendedKeys: string[]): { recommended: ModuleInfo[]; goodToHave: ModuleInfo[] } {
  const rec = new Set(completeModules(catalogue, recommendedKeys))
  return {
    recommended: arrangeModules(catalogue, [...rec]),
    goodToHave: arrangeModules(catalogue, catalogue.map((m) => m.key).filter((k) => !rec.has(k))),
  }
}

/** View 2, 'By package' (W15-R27): the modules a launch package includes, in display order. */
export function modulesOfPackage(catalogue: ModuleInfo[], pkg: LaunchPackageId): ModuleInfo[] {
  return arrangeModules(catalogue, allowedModules(catalogue, pkg))
}

/** What a package adds to the one before it (W15-R30): Root none, Square its modules, Grove the rest. The Event pass is its own list, not a step of that ladder. */
export function packageAdditions(catalogue: ModuleInfo[], pkg: LaunchPackageId): ModuleInfo[] {
  const ladder: LaunchPackageId[] = ['roots', 'square', 'grove']
  const own = modulesOfPackage(catalogue, pkg)
  if (pkg === 'event' || pkg === 'roots') return own
  const before = new Set(allowedModules(catalogue, ladder[ladder.indexOf(pkg) - 1]!))
  return arrangeModules(catalogue, own.map((m) => m.key).filter((k) => !before.has(k)))
}

/** What is on when a square of the package is created: the starter set of its kind of group (the cultural set is the Recommended modules), limited to what the package allows. */
export function startingModules(catalogue: ModuleInfo[], pkg: LaunchPackageId, starter?: StarterSetInfo): string[] {
  const allowed = new Set(allowedModules(catalogue, pkg))
  if (pkg === 'event') return [...allowed]
  // the kind's list is the whole truth (W15-R27): a sub-switch is on only when the list names it (Coupons and Check-in are in the cultural list)
  return completeModules(catalogue, starter ? starter.modules : recommendedModules(catalogue)).filter((k) => allowed.has(k))
}

/** The starter sets for the mock mode and as the fallback; the server's list (backend/app/platform/starter_sets.py) is the one that counts. */
export const MOCK_STARTER_SETS: StarterSetInfo[] = [
  { key: 'cultural', label: 'Cultural group', description: 'Events and tickets with coupons and check-in, payments, members, messages, a gallery, news, a committee page and accounting.', modules: ['events', 'tickets', 'coupons', 'checkin', 'payments', 'members', 'messages', 'gallery', 'committee', 'news', 'accounting'] },
  { key: 'religious', label: 'Religious community', description: 'Gatherings and events, a member list, donations, messages to the community, news, a gallery and a committee page. No ticket sales or paid memberships to begin with.', modules: ['events', 'payments', 'members', 'donations', 'messages', 'news', 'gallery', 'committee'] },
  { key: 'band', label: 'Band or artist', description: 'Gigs and tickets, news, a gallery, a newsletter, messages to fans, donations, sponsors and testimonials. No member list or accounting to begin with.', modules: ['events', 'tickets', 'payments', 'news', 'gallery', 'newsletter', 'messages', 'donations', 'sponsors', 'testimonials'] },
  { key: 'charity', label: 'Charity or fundraiser', description: 'Donations, events, news, a gallery, messages and a newsletter to supporters, sponsors and accounting.', modules: ['donations', 'payments', 'events', 'news', 'gallery', 'messages', 'newsletter', 'sponsors', 'accounting'] },
]
