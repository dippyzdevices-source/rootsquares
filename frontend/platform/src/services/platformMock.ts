// In-browser mock of the platform API (VITE_USE_MOCK=true): same interface, data kept in localStorage, provisioning finishes after 1.5 s.
// Mock only: passwords are stored in clear text in the browser.
import { THEMES } from '@rootsquares/ui/themes'
import { MOCK_MODULES, MOCK_STARTER_SETS, allowedModules, completeModules, startingModules } from './modulesCatalogue'
import { ApiError, type SiteDomain, type MailDomain, type BillingOrder, type CorePart, type InvoiceSeller, type Prospect, type EventPassInfo, type PlanPrice, type PlatformSquare, type PlatformVoucher } from '@rootsquares/ui/types/platformTypes'
import { type Invoice, type PortalAttention, type PlatformApi, type PlatformUser, type Analytics, type SupportAuditRow, type SupportGrant, type SupportState } from '@/services/platformTypes'

interface MockUser extends PlatformUser { password: string }
interface Db { users: MockUser[]; squares: (PlatformSquare & { owner_id: string })[]; session: string | null }
const KEY = 'rs-mock-platform'
const mockOrders: BillingOrder[] = [] // billing orders last until reload
const mockAnalytics = new Map<string, boolean>() // the owner's switch per square lasts until reload (W23-R79)
const mockSupport = new Map<string, { grant: SupportGrant | null; audit: SupportAuditRow[] }>() // support access per square lasts until reload (W23-R67)
const MOCK_PRICES: PlanPrice[] = [
  { key: 'launch.roots', amount_minor: 14_900, currency: 'USD', interval: 'one_off' }, { key: 'launch.square', amount_minor: 29_900, currency: 'USD', interval: 'one_off' },
  { key: 'launch.grove', amount_minor: 39_900, currency: 'USD', interval: 'one_off' }, { key: 'launch.event', amount_minor: 2_500, currency: 'USD', interval: 'one_off' },
  { key: 'running.keep.month', amount_minor: 500, currency: 'USD', interval: 'month' }, { key: 'running.keep.year', amount_minor: 5_000, currency: 'USD', interval: 'year' },
  { key: 'running.live.month', amount_minor: 2_500, currency: 'USD', interval: 'month' }, { key: 'running.live.year', amount_minor: 25_000, currency: 'USD', interval: 'year' },
]
const ENABLED_THEMES = ['paper-brick']
type MockDomain = { request?: { domain: string; local: string }; domain?: string; local: string; status?: string; help?: boolean }
const mailDomains: Record<string, MockDomain> = {}
const mockMailDomain = (id: string): MailDomain => {
  const sq = db.squares.find((s) => s.id === id)
  const cur = mailDomains[id]
  const verified = cur?.status === 'verified'
  const state = verified ? 'verified' : cur?.domain ? 'registered' : cur?.request ? 'requested' : 'none'
  return {
    allowed: sq?.launch_package === 'grove', available: true, domain: cur?.domain ?? null, local_part: cur?.local ?? 'hello', status: cur?.domain ? (cur.status ?? 'not_started') : null, verified,
    from_address: cur?.domain && verified ? `${cur.local}@${cur.domain}` : null,
    records: cur?.domain ? [
      { record: 'DKIM', type: 'TXT', name: 'resend._domainkey', value: 'p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNAD...', priority: null, status: cur.status ?? 'not_started' },
      { record: 'SPF', type: 'MX', name: 'send', value: 'feedback-smtp.eu-west-1.amazonses.com', priority: 10, status: cur.status ?? 'not_started' },
      { record: 'SPF', type: 'TXT', name: 'send', value: 'v=spf1 include:amazonses.com ~all', priority: null, status: cur.status ?? 'not_started' },
    ] : [],
    state, requested_domain: cur?.request?.domain ?? null, requested_local: cur?.request?.local ?? null, requested_at: cur?.request ? new Date().toISOString() : null, help_requested: !!cur?.help, auto_approve: true,
  }
}
// The own website domain, in the browser only: staff would add it on the host; here a request is activated after two seconds and the first check finds the DNS.
type MockSite = { request?: string; domain?: string; help?: boolean }
const siteDomains: Record<string, MockSite> = {}
const mockSiteDomain = (id: string, dns: SiteDomain['dns'] = 'unchecked'): SiteDomain => {
  const sq = db.squares.find((s) => s.id === id)
  const cur = siteDomains[id]
  return {
    allowed: sq?.launch_package === 'grove', target: 'squares.rootsquares.com', state: cur?.domain ? 'active' : cur?.request ? 'requested' : 'none',
    domain: cur?.domain ?? null, requested_domain: cur?.request ?? null, requested_at: cur?.request ? new Date().toISOString() : null, default_domain: sq?.domain ?? '', help_requested: !!cur?.help, dns, render: 'off',
  }
}
const RESERVED_SLUGS = ['www', 'api', 'admin', 'admin-api', 'mail', 'login', 'support', 'rootsquares'] // a short sample of backend/app/platform/reserved_slugs.py (mock only)
/** The clock of a new Event pass in the mock: 45 days live, 45 days archive, deleted 14 days after (ADR 044) */
function mockEventPass(now: Date): EventPassInfo {
  const day = 86_400_000
  const live = new Date(now.getTime() + 45 * day)
  const archive = new Date(live.getTime() + 45 * day)
  return { phase: 'live', started_at: now.toISOString(), live_until: live.toISOString(), archive_until: archive.toISOString(), purge_at: null, days_left: 45, export_confirmed_at: null, reminders_sent: [] }
}
const delay = <T>(v: T, ms = 150): Promise<T> => new Promise((r) => setTimeout(() => r(structuredClone(v)), ms))
const uid = () => crypto.randomUUID()

function load(): Db {
  try { const v = JSON.parse(localStorage.getItem(KEY) ?? 'null') as Db | null; if (v) return v } catch { /* start fresh */ }
  return { users: [], squares: [], session: null }
}
let db = load()
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(db)) } catch { /* storage unavailable: the mock lasts until reload */ } }
const strip = ({ password: _p, ...u }: MockUser): PlatformUser => u
const current = (): MockUser => {
  const u = db.users.find((x) => x.id === db.session)
  if (!u) throw new ApiError(401, 'unauthorized', 'Sign in to continue')
  return u
}
const pub = ({ owner_id: _o, ...s }: PlatformSquare & { owner_id: string }): PlatformSquare => s


// vouchers and partners of the in-browser mock (W14-R27)
const mockVouchers: PlatformVoucher[] = []
const MOCK_CORE: CorePart[] = [
  { key: 'home', label: 'Home', description: 'The front page of the site.', needs: [] },
  { key: 'about', label: 'About', description: 'The About page.', needs: [] },
  { key: 'contact', label: 'Contact', description: 'The Contact page and its form.', needs: [] },
  { key: 'legal', label: 'Legal pages', description: 'Privacy, terms and the other legal pages.', needs: [] },
  { key: 'login', label: 'Sign-in', description: 'Sign-in and sign-up for members and admins.', needs: [] },
  { key: 'account', label: 'Member account', description: "The member's own pages: profile and what they bought or joined.", needs: ['login'] },
  { key: 'admin', label: 'Admin', description: 'The admin area where the site is run.', needs: ['login'] },
  { key: 'settings', label: 'Settings', description: "The square's settings in the admin.", needs: ['admin'] },
  { key: 'media', label: 'Media', description: 'The media store for pictures and files.', needs: ['admin'] },
]
const mockProspects: Prospect[] = [] // prospects last until reload
const mockSeller: InvoiceSeller = { name: '', org_no: '', address: '', email: '', prefix: 'RS', footer: '' }

export const platformMock: PlatformApi = {
  async me() { return delay(strip(current())) },
  async signup(input) {
    if (db.users.some((u) => u.email === input.email.toLowerCase())) throw new ApiError(409, 'email_taken', 'An account with this email already exists')
    const u: MockUser = { id: uid(), email: input.email.toLowerCase(), password: input.password, name: input.name, organizations: [{ id: uid(), name: input.organization_name, role: 'owner' }] }
    db.users.push(u); db.session = u.id; save()
    return delay(strip(u))
  },
  async login(email, password) {
    const u = db.users.find((x) => x.email === email.toLowerCase())
    if (!u || u.password !== password) throw new ApiError(401, 'invalid_credentials', 'Email or password is wrong')
    db.session = u.id; save()
    return delay(strip(u))
  },
  async logout() { db.session = null; save(); return delay(undefined) },
  async createOrganization(name) {
    const u = current()
    u.organizations.push({ id: uid(), name: name.trim(), role: 'owner' }); save()
    return delay(strip(u))
  },
  async listSquares() {
    const u = current()
    return delay(db.squares.filter((s) => s.owner_id === u.id).map(pub))
  },
  async createSquare(input) {
    const u = current()
    if (!ENABLED_THEMES.includes(input.theme_id)) throw new ApiError(422, 'validation_error', 'Theme is not available', [{ loc: ['theme_id'], msg: 'theme is not enabled' }])
    if (RESERVED_SLUGS.includes(input.slug)) throw new ApiError(409, 'slug_reserved', 'This address is not available')
    if (db.squares.some((s) => s.slug === input.slug)) throw new ApiError(409, 'slug_taken', 'This address is taken')
    const sq: PlatformSquare & { owner_id: string } = { id: uid(), org_id: u.organizations[0]?.id ?? uid(), org_name: u.organizations[0]?.name ?? '', owner_id: u.id, name: input.name, slug: input.slug, theme_id: input.theme_id, currency: input.currency ?? 'NOK', phone_country: input.phone_country ?? 'NO', modules: completeModules(MOCK_MODULES, input.modules ?? startingModules(MOCK_MODULES, input.launch_package ?? 'square', MOCK_STARTER_SETS.find((s) => s.key === input.group_type))), launch_package: input.launch_package ?? 'square', group_type: input.launch_package === 'event' ? null : (input.group_type ?? 'cultural'), running_plan: input.launch_package === 'event' ? 'event' : 'live', event_pass: input.launch_package === 'event' ? mockEventPass(new Date()) : null, allowed_modules: allowedModules(MOCK_MODULES, input.launch_package ?? 'square'), logo_url: null, logo_dark_url: null, status: 'provisioning', domain: `${input.slug}.rootsquares.com`, url: `https://${input.slug}.rootsquares.com`, has_database: false, error: null, created_at: new Date().toISOString(), google_login: 'requested', auth_callback_url: null }
    db.squares.unshift(sq); save()
    setTimeout(() => { sq.status = 'ready'; sq.has_database = true; save() }, 1500)
    return delay(pub(sq))
  },
  async getSquare(id) {
    const u = current()
    const sq = db.squares.find((s) => s.id === id)
    if (!sq || sq.owner_id !== u.id) throw new ApiError(404, 'not_found', 'Square not found')
    return delay(pub(sq))
  },
  async getSupport(id) {
    const m = mockSupport.get(id) ?? { grant: null, audit: [] }
    if (m.grant && new Date(m.grant.expires_at) <= new Date()) m.grant = null
    return delay({ grant: m.grant, requests: [], can_manage: true } as SupportState)
  },
  async getAnalytics(id, days) {
    const on = mockAnalytics.get(id) ?? false
    const end = new Date()
    const daily = Array.from({ length: days }, (_, i) => {
      const d = new Date(end.getTime() - (days - 1 - i) * 86400000)
      const v = on ? 8 + ((i * 7) % 23) : 0
      return { day: d.toISOString().slice(0, 10), visits: v, views: v * 3, visitors: Math.max(1, v - 2) }
    })
    const sum = (k: 'visits' | 'views' | 'visitors') => daily.reduce((a, d) => a + d[k], 0)
    return delay({
      enabled: on, reachable: true, resting: false, counting: on, days, start: daily[0]?.day ?? null, end: daily.at(-1)?.day ?? null, daily,
      totals: { visits: sum('visits'), views: sum('views'), visitors: sum('visitors') }, previous: { visits: Math.round(sum('visits') * 0.8), views: Math.round(sum('views') * 0.9), visitors: Math.round(sum('visitors') * 0.85) },
      pages: on ? [{ path: '/', views: 120, few: false }, { path: '/events', views: 64, few: false }, { path: '/gallery', views: null, few: true }] : [],
      sources: on ? [{ source: 'direct', visits: 80, few: false }, { source: 'google.com', visits: 31, few: false }] : [],
      events: on ? [{ slug: 'autumn', title: 'Autumn gathering', views: 52, views_few: false, tickets: null, tickets_few: true }] : [],
    } as Analytics)
  },
  async setAnalytics(id, enabled) {
    mockAnalytics.set(id, enabled)
    return platformMock.getAnalytics(id, 30)
  },
  async getSupportActivity(id, page, perPage = 15) {
    const all = mockSupport.get(id)?.audit ?? []
    return delay({ items: all.slice((page - 1) * perPage, page * perPage), page, per_page: perPage, total: all.length })
  },
  async createSupportGrant(id, input) {
    const m = mockSupport.get(id) ?? { grant: null, audit: [] }
    if (m.grant && new Date(m.grant.expires_at) > new Date()) throw new ApiError(409, 'grant_active', 'A support grant is already active. Revoke it first.')
    const now = new Date()
    const grant: SupportGrant = { id: uid(), created_at: now.toISOString(), expires_at: new Date(now.getTime() + input.duration_minutes * 60000).toISOString(), duration_minutes: input.duration_minutes, scopes: input.scopes, allow_changes: input.allow_changes, note: input.note ?? null, sessions: [] }
    m.grant = grant
    m.audit = [{ at: now.toISOString(), action: 'support.grant', who: 'You', by_you: true, scopes: input.scopes, allow_changes: input.allow_changes, ended_by: null }, ...m.audit]
    mockSupport.set(id, m)
    return delay(grant)
  },
  async revokeSupport(id) {
    const m = mockSupport.get(id)
    if (!m?.grant) throw new ApiError(404, 'not_found', 'There is no active support grant')
    m.audit = [{ at: new Date().toISOString(), action: 'support.revoke', who: 'You', by_you: true, scopes: m.grant.scopes, allow_changes: null, ended_by: null }, ...m.audit]
    m.grant = null
    return delay({ grant: null, requests: [], can_manage: true } as SupportState)
  },
  async getModuleStatus() {
    return delay({ available: false, items: [] }) // the in-browser mock has no square server to ask
  },
  async getSquareHealth() {
    return delay({
      reachable: true, version: '',
      checks: [
        { key: 'reachable', group: 'system', state: 'ok', text: "The site's server answers." },
        { key: 'database', group: 'system', state: 'ok', text: 'The database answers.' },
        { key: 'storage', group: 'system', state: 'ok', text: 'Storage for pictures and files is set up.' },
        { key: 'job_messages', group: 'jobs', state: 'ok', text: 'Messages scheduler: running.' },
        { key: 'setup_email', group: 'setup', state: 'warn', text: 'Email sending is not set up, so no emails go out.' },
        { key: 'site_logo', group: 'setup', state: 'warn', text: 'No logo is set yet.' },
      ],
    })
  },
  async listModules() {
    return delay(MOCK_MODULES)
  },
  async moduleCatalogue() {
    return delay({ items: MOCK_MODULES, core: MOCK_CORE, module_core_needs: Object.fromEntries(MOCK_MODULES.map((m) => [m.key, ['tickets', 'memberships', 'volunteering'].includes(m.key) ? ['admin', 'account'] : ['admin']])) })
  },
  async listStarterSets() {
    return delay(MOCK_STARTER_SETS)
  },
  async submitProspect(input) {
    if (!input.website) mockProspects.unshift({ id: uid(), name: input.name, email: input.email, phone: input.phone, message: input.message ?? null, source: 'pricing_custom', status: 'new', notes: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString() })
    return delay(undefined)
  },
  async getTaxRates() {
    return { NO: 25 }
  },
  async getPrices() {
    return delay(MOCK_PRICES)
  },
  async voucherPreview(input) { return this.voucherCheck('', { kind: input.kind === 'event_pass' ? 'event_pass' : 'first', interval: 'month', launch_package: input.launch_package, code: input.code } as never) },
  async voucherCheck(_id, input) {
    const v = mockVouchers.find((x) => x.code === input.code.trim().toUpperCase() && x.active)
    if (!v) return delay({ valid: false, reason: 'voucher_unknown', message: 'This code is not valid.', list_minor: 0, discount_minor: 0, payable_minor: 0 })
    const list = MOCK_PRICES.find((p) => p.key === (input.kind === 'event_pass' ? 'launch.event' : `launch.${(input as { launch_package?: string }).launch_package ?? 'roots'}`))?.amount_minor ?? 0
    const discount = Math.min(list, v.kind === 'percent' ? Math.round((list * v.value) / 100) : v.value)
    return delay({ valid: true, list_minor: list, discount_minor: discount, payable_minor: list - discount })
  },
  async startCheckout(id, input) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    const price = (key: string) => MOCK_PRICES.find((p) => p.key === key)!.amount_minor
    const ladder = ['roots', 'square', 'grove']
    let amount: number
    if (input.kind === 'event_pass' || input.kind === 'first') throw new ApiError(409, 'not_awaiting_payment', 'This Event pass is already paid')
    if (input.kind === 'upgrade') {
      const from = ladder.indexOf(sq.launch_package)
      const to = ladder.indexOf(input.launch_package)
      if (to < 0 || to <= from) throw new ApiError(409, 'no_upgrade', 'There is nothing to upgrade to')
      amount = price(`launch.${input.launch_package}`) - price(`launch.${sq.launch_package}`)
    } else if (input.kind === 'event_upgrade') {
      if (!sq.event_pass || sq.event_pass.phase === 'removed') throw new ApiError(409, 'not_event_pass', 'Only a running Event pass can be upgraded')
      if (!ladder.includes(input.launch_package)) throw new ApiError(400, 'bad_plan', 'Choose a launch package and a monthly or yearly period')
      amount = Math.max(0, price(`launch.${input.launch_package}`) - price('launch.event')) + price(`running.live.${input.interval}`)
    } else {
      if (sq.running_plan === 'event') throw new ApiError(409, 'event_pass', 'An event pass has no running plan to buy')
      amount = price(`running.${input.running_plan}.${input.interval}`)
    }
    const order: BillingOrder = { id: uid(), square_id: id, kind: input.kind, launch_package: input.kind === 'running' ? null : input.launch_package, running_plan: input.kind === 'running' ? input.running_plan : input.kind === 'event_upgrade' ? 'live' : null, interval: input.kind === 'upgrade' ? null : input.interval, amount_minor: amount, currency: 'USD', status: 'pending', provider: 'fake', created_at: new Date().toISOString(), paid_at: null }
    mockOrders.push(order)
    return delay({ order_id: order.id, url: `/billing/checkout?order=${order.id}` })
  },
  async getOrder(orderId) {
    const o = mockOrders.find((x) => x.id === orderId)
    if (!o) throw new ApiError(404, 'not_found', 'Order not found')
    return delay(o)
  },
  async getInvoice(orderId) {
    const o = mockOrders.find((x) => x.id === orderId)
    if (!o) throw new ApiError(404, 'not_found', 'Order not found')
    if (o.status !== 'paid' && o.status !== 'refunded') throw new ApiError(409, 'not_paid', 'Only a paid payment has an invoice')
    const sq = db.squares.find((x) => x.id === o.square_id)
    const paid = o.paid_at ?? o.created_at
    const n = mockOrders.filter((x) => (x.status === 'paid' || x.status === 'refunded') && (x.paid_at ?? x.created_at).slice(0, 4) === paid.slice(0, 4) && (x.paid_at ?? x.created_at) <= paid).length
    const inv: Invoice = { number: `${mockSeller.prefix || 'RS'}-${paid.slice(0, 4)}-${String(n).padStart(4, '0')}`, issued_at: paid, seller: { ...mockSeller }, buyer_name: current().name, square_name: sq?.name ?? '', country: null, tax_percent: 0, net_minor: o.amount_minor, tax_minor: 0, period_start: null, period_end: null, order: o }
    return delay(inv)
  },
  async confirmOrder(id, orderId) {
    const order = (await platformMock.listOrders(id)).find((o) => o.id === orderId)
    if (!order) throw new ApiError(404, 'not_found', 'Order not found')
    return order // the mock checkout pays or cancels at once: there is nothing to ask
  },
  async listOrders(id) {
    return delay(mockOrders.filter((o) => o.square_id === id).reverse())
  },
  async fakeConfirm(orderId, outcome) {
    const o = mockOrders.find((x) => x.id === orderId)
    if (!o) throw new ApiError(404, 'not_found', 'Order not found')
    if (o.status === 'pending') {
      o.status = outcome === 'paid' ? 'paid' : 'cancelled'
      if (outcome === 'paid') {
        o.paid_at = new Date().toISOString()
        const sq = db.squares.find((s) => s.id === o.square_id)
        if (sq && o.kind === 'upgrade' && o.launch_package) { sq.launch_package = o.launch_package; sq.allowed_modules = allowedModules(MOCK_MODULES, o.launch_package) }
        if (sq && o.kind === 'event_upgrade' && o.launch_package) {
          sq.launch_package = o.launch_package
          sq.running_plan = 'live'
          sq.event_pass = null
          sq.allowed_modules = allowedModules(MOCK_MODULES, o.launch_package)
          sq.paid_until = new Date(Date.now() + (o.interval === 'year' ? 365 : 30) * 86_400_000).toISOString()
        }
        if (sq && o.kind === 'running' && o.running_plan) { sq.running_plan = o.running_plan; sq.paid_until = new Date(Date.now() + (o.interval === 'year' ? 365 : 30) * 86_400_000).toISOString() }
        save()
      }
    }
    return delay(o)
  },
  async confirmEventPassExport(id) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (!sq.event_pass) throw new ApiError(409, 'not_event_pass', 'This square is not an Event pass')
    sq.event_pass.export_confirmed_at = new Date().toISOString()
    save()
    return delay(pub(sq))
  },
  async billingPortal() { throw new ApiError(409, 'no_customer', 'There is no payment on record yet') },
  async cancelRenewal() { throw new ApiError(409, 'no_subscription', 'This square has no renewing payment') },
  async resumeRenewal() { throw new ApiError(409, 'no_subscription', 'This square has no renewing payment') },
  async setBillingInterval(id, interval) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    sq.billing_interval = interval
    save()
    return delay(pub(sq))
  },
  async setRunningPlan(id, plan) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (sq.running_plan === 'event') throw new ApiError(409, 'event_pass', 'An event pass cannot be switched this way')
    sq.running_plan = plan
    sq.sleep_state = plan === 'keep' ? 'sleeping' : 'awake'
    save()
    return delay(pub(sq))
  },
  async changePlan(id, plan) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (sq.running_plan === 'event') throw new ApiError(409, 'event_pass', 'An event pass has no plan to change')
    if (plan === 'keep') {
      if (sq.running_plan === 'keep' || sq.pending_plan === 'keep') throw new ApiError(409, 'same_plan', 'Already on Keep or going there')
      sq.pending_plan = 'keep' // from the next renewal: the site stays live
    } else if (sq.running_plan === 'live') {
      if (sq.pending_plan !== 'keep') throw new ApiError(409, 'same_plan', 'Already on Live')
      sq.pending_plan = null
    } else {
      sq.running_plan = 'live'
      sq.sleep_state = 'awake'
      sq.pending_plan = null
    }
    save()
    return delay(pub(sq))
  },
  async setSquareModules(id, modules) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    const outside = modules.filter((k) => !sq.allowed_modules.includes(k))
    if (outside.length) throw new ApiError(403, 'module_not_in_package', `Not in your launch package: ${outside.join(', ')}`)
    sq.modules = completeModules(MOCK_MODULES, modules)
    save()
    return delay(pub(sq))
  },
  async setSquareLook(id, look) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    const has = !!look && !!(look.colors || look.colors_dark || look.fonts || look.spinners?.length || (look.shape && Object.keys(look.shape).length) || (look.feel && Object.keys(look.feel).length) || look.type)
    if (has && (sq.launch_package === 'roots' || sq.launch_package === 'event')) throw new ApiError(403, 'package_required', 'Own colours and fonts are in the Square package and above')
    sq.theme_overrides = has ? { colors: look!.colors, colors_dark: look!.colors_dark ?? null, fonts: look!.fonts, spinners: look!.spinners?.length ? look!.spinners : null, shape: look!.shape && Object.keys(look!.shape).length ? look!.shape : null, feel: look!.feel && Object.keys(look!.feel).length ? look!.feel : null, type: look!.type ?? null } : null
    save()
    return delay(pub(sq))
  },
  async saveLookDraft(id, look, options = {}) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (sq.launch_package === 'roots' || sq.launch_package === 'event') throw new ApiError(403, 'package_required', 'Own colours and fonts are in the Square package and above')
    if (!(look.colors || look.colors_dark || look.fonts || look.spinners?.length || (look.shape && Object.keys(look.shape).length) || (look.feel && Object.keys(look.feel).length) || look.type)) throw new ApiError(422, 'validation_failed', 'choose something to share first')
    const old = sq.look_draft
    sq.look_draft = {
      look: { colors: look.colors, colors_dark: look.colors_dark ?? null, fonts: look.fonts, spinners: look.spinners?.length ? look.spinners : null, shape: look.shape && Object.keys(look.shape).length ? look.shape : null, feel: look.feel && Object.keys(look.feel).length ? look.feel : null, type: look.type ?? null },
      theme_id: options.themeId ?? null,
      token: old && !options.renew ? old.token : Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2),
      expires_at: new Date(Date.now() + 14 * 86400000).toISOString(),
      expired: false,
      has_passcode: options.passcode === undefined ? !!old?.has_passcode : options.passcode.trim() !== '',
    }
    save()
    return delay(pub(sq))
  },
  async saveLookSeasons(id, seasons) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (sq.launch_package === 'roots' || sq.launch_package === 'event') throw new ApiError(403, 'package_required', 'Own colours and fonts are in the Square package and above')
    for (const s of seasons) {
      if (!s.name?.trim() || !s.start || !s.end || (!s.yearly && s.end < s.start)) throw new ApiError(422, 'validation_failed', 'A seasonal look is not valid')
      const l = s.look
      if (!(l.colors || l.colors_dark || l.fonts || l.spinners?.length || (l.shape && Object.keys(l.shape).length) || (l.feel && Object.keys(l.feel).length) || l.type)) throw new ApiError(422, 'validation_failed', 'a season needs a look: choose something in the tabs first')
    }
    sq.look_seasons = seasons.map((s) => ({ ...s, id: s.id ?? Math.random().toString(36).slice(2, 10) }))
    save()
    return delay(pub(sq))
  },
  async removeLookDraft(id) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    sq.look_draft = null
    save()
    return delay(pub(sq))
  },
  async publishLookDraft(id) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (!sq.look_draft) throw new ApiError(404, 'not_found', 'There is no draft to publish')
    sq.theme_overrides = sq.look_draft.look
    if (sq.look_draft.theme_id && THEMES.some((t) => t.id === sq.look_draft!.theme_id)) sq.theme_id = sq.look_draft.theme_id
    sq.look_draft = null
    save()
    return delay(pub(sq))
  },
  // The square's own sending domain, in the browser only: staff would set it up and the DNS would be found; here a request is set up after two seconds and the first check finds it.
  async getSiteDomain(id) {
    return delay(mockSiteDomain(id))
  },
  async requestSiteDomain(id, input) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (sq.launch_package !== 'grove') throw new ApiError(403, 'package_required', 'An own website domain is in the Grove package')
    const domain = input.trim().toLowerCase()
    if (!/^([a-z0-9-]+\.)+[a-z]{2,}$/.test(domain)) throw new ApiError(422, 'site_domain_invalid', 'This is not a domain name')
    const cur = (siteDomains[id] ??= {})
    cur.request = domain
    window.setTimeout(() => { if (cur.request) { cur.domain = cur.request; cur.request = undefined } }, 2000)
    return delay(mockSiteDomain(id))
  },
  async withdrawSiteDomainRequest(id) {
    if (siteDomains[id]) siteDomains[id].request = undefined
    return delay(mockSiteDomain(id))
  },
  async askSiteDomainHelp(id) {
    const cur = (siteDomains[id] ??= {})
    cur.help = true
    return delay(mockSiteDomain(id))
  },
  async checkSiteDomain(id) {
    if (!siteDomains[id]?.domain && !siteDomains[id]?.request) throw new ApiError(409, 'site_domain_missing', 'There is no domain to check yet')
    return delay(mockSiteDomain(id, 'pointing'))
  },
  async removeSiteDomain(id) {
    delete siteDomains[id]
    return delay(mockSiteDomain(id))
  },
  async getMailDomain(id) {
    return delay(mockMailDomain(id))
  },
  async requestMailDomain(id, input) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (sq.launch_package !== 'grove') throw new ApiError(403, 'package_required', 'An own sending domain is in the Grove package')
    const domain = input.domain.trim().toLowerCase()
    if (!/^([a-z0-9-]+\.)+[a-z]{2,}$/.test(domain)) throw new ApiError(422, 'mail_domain_invalid', 'This is not a domain name')
    const cur = (mailDomains[id] ??= { local: 'hello' })
    cur.request = { domain, local: input.local_part.trim().toLowerCase() || 'hello' }
    window.setTimeout(() => { if (cur.request) { cur.domain = cur.request.domain; cur.local = cur.request.local; cur.status = 'not_started'; cur.request = undefined } }, 2000)
    return delay(mockMailDomain(id))
  },
  async withdrawMailDomainRequest(id) {
    if (mailDomains[id]) mailDomains[id].request = undefined
    return delay(mockMailDomain(id))
  },
  async setMailFromName(id, localPart) {
    if (mailDomains[id]) mailDomains[id].local = localPart.trim().toLowerCase() || 'hello'
    return delay(mockMailDomain(id))
  },
  async checkMailDomain(id) {
    const cur = mailDomains[id]
    if (!cur?.domain) throw new ApiError(409, 'mail_domain_missing', 'There is no registered domain to check yet')
    cur.status = 'verified'
    return delay(mockMailDomain(id))
  },
  async removeMailDomain(id) {
    delete mailDomains[id]
    return delay(mockMailDomain(id))
  },
  async sendMailDomainInstructions(id) {
    return delay(mockMailDomain(id))
  },
  async askMailDomainHelp(id) {
    const cur = (mailDomains[id] ??= { local: 'hello' })
    cur.help = true
    return delay(mockMailDomain(id))
  },
  async getAttention() {
    // in the browser only: a registered own sending domain that is not verified yet is the one thing that waits
    const items: PortalAttention[] = Object.entries(mailDomains)
      .filter(([, d]) => d.domain && d.status !== 'verified')
      .map(([id, d]) => {
        const sq = db.squares.find((s) => s.id === id)
        return { kind: 'mail_domain_records' as const, square_id: id, name: sq?.name ?? '', slug: sq?.slug ?? '', detail: d.domain ?? null, since: new Date().toISOString() }
      })
    return delay({ items, count: items.length })
  },
  async setMailContact(id, email) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    const v = (email ?? '').trim().toLowerCase()
    if (v && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) throw new ApiError(422, 'validation_failed', 'This is not an e-mail address')
    sq.mail_contact_email = v || null
    save()
    return delay(pub(sq))
  },
  async setSquareTheme(id, themeId) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (!THEMES.some((t) => t.id === themeId)) throw new ApiError(422, 'validation_failed', 'Theme is not available')
    sq.theme_id = themeId
    save()
    return delay(pub(sq))
  },
  async uploadSquareLogo(id, file, variant = 'light') {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (variant === 'dark') sq.logo_dark_url = URL.createObjectURL(file)
    else sq.logo_url = URL.createObjectURL(file)
    save()
    return delay(pub(sq))
  },
  async removeSquareLogo(id, variant = 'light') {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (variant === 'dark') sq.logo_dark_url = null
    else sq.logo_url = null
    save()
    return delay(pub(sq))
  },
  async deleteSquare(id, confirmSlug) {
    const u = current()
    const sq = db.squares.find((s) => s.id === id && s.owner_id === u.id)
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    if (sq.status === 'provisioning') throw new ApiError(409, 'still_provisioning', 'The square is still being set up')
    if (confirmSlug.trim().toLowerCase() !== sq.slug) throw new ApiError(422, 'confirm_mismatch', 'The address does not match')
    db.squares = db.squares.filter((s) => s.id !== id); save()
    return delay(undefined)
  },
  async exportMyData() {
    const u = strip(current())
    return new Blob([JSON.stringify({ account: u, squares: db.squares.filter((s) => s.owner_id === u.id).map(pub) }, null, 2)], { type: 'application/json' })
  },
  async deleteAccount(confirmEmail) {
    const u = current()
    if (confirmEmail.trim().toLowerCase() !== u.email) throw new ApiError(422, 'confirm_mismatch', 'The address does not match')
    const mine = db.squares.filter((s) => s.owner_id === u.id)
    if (mine.length) throw new ApiError(409, 'has_squares', 'Delete your squares first.', [], { squares: mine.map((s) => ({ id: s.id, name: s.name, slug: s.slug })) })
    db.users = db.users.filter((x) => x.id !== u.id); db.session = null; save()
    return delay(true)
  },
  async getPublicSquare(slug) {
    const sq = db.squares.find((s) => s.slug === slug.toLowerCase() && s.status === 'ready')
    if (!sq) throw new ApiError(404, 'not_found', 'Square not found')
    return delay({ name: sq.name, slug: sq.slug, theme_id: sq.theme_id, domain: sq.domain, google_login: sq.google_login, has_auth_project: true, database: { ok: true, admins: 1 }, auth_url: null, auth_public_key: null })
  },
  async getPublicSquareByHost(host) {
    return this.getPublicSquare(host.replace(/\.localhost$/, ''))
  },
  async getSquareMe() {
    throw new ApiError(401, 'unauthorized', 'Sign in to this square')
  },
  async retrySquare(id) {
    const sq = db.squares.find((s) => s.id === id)
    if (!sq || sq.owner_id !== current().id) throw new ApiError(404, 'not_found', 'Square not found')
    if (sq.status !== 'failed') throw new ApiError(409, 'not_failed', 'Only a failed square can be tried again')
    sq.status = 'provisioning'; sq.error = null; save()
    setTimeout(() => { sq.status = 'ready'; sq.has_database = true; save() }, 1500)
    return delay(pub(sq))
  },

}
