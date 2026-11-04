// The types of the platform API that only the customer app uses (ADR 084 stage 3d); the shared ones are in @rootsquares/ui/types/platformTypes.
import type { PlanPrice, BillingOrder, InvoiceSeller, LaunchPackageId, ThemeLook, LookSeason, PlatformSquare, ModuleCatalogue, ModuleInfo, MailDomain, SiteDomain } from '@rootsquares/ui/types/platformTypes'

/** One thing that waits for the owner of a square (W25-R35): the records of the own sending domain to add, a domain that failed, staff asking for support access. */
export interface PortalAttention { kind: 'mail_domain_records' | 'mail_domain_failed' | 'support_request'; square_id: string; name: string; slug: string; detail: string | null; since: string }
export interface PortalAttentionList { items: PortalAttention[]; count: number }

export interface Org { id: string; name: string; role: string; billing_country?: string | null }
export interface PlatformUser { id: string; email: string; name: string; organizations: Org[] }
export interface ProspectInput { name: string; email: string; phone: string; message?: string; consent: boolean; website?: string }
/** The invoice of a paid payment (W19-R16): the order plus the seller, the buyer, the number, the tax split and the period it pays for */
export interface Invoice {
  number: string; issued_at: string; seller: InvoiceSeller; buyer_name: string; square_name: string; country: string | null
  tax_percent: number; net_minor: number; tax_minor: number; period_start: string | null; period_end: string | null; order: BillingOrder
}
/** A code that lowers a launch package or an Event pass once (W14-R27); sent next to the payment it is for */
export type VoucherCode = { voucher_code?: string }
export type CheckoutInput = VoucherCode & (
  | { kind: 'upgrade'; launch_package: LaunchPackageId }
  | { kind: 'running'; running_plan: 'live' | 'keep'; interval: 'month' | 'year' }
  /** An Event pass becomes a launch package plus Live; the price of the pass is credited (W11, ADR 044) */
  | { kind: 'event_upgrade'; launch_package: LaunchPackageId; interval: 'month' | 'year' }
  /** The $25 of a new Event pass that is not built until it is paid (W12-R6) */
  | { kind: 'event_pass' }
  /** The first payment when the trial ends: the launch package plus the first Live period in one checkout (W12-R9) */
  | { kind: 'first'; interval: 'month' | 'year'; launch_package?: LaunchPackageId }
)
export interface VoucherCheck {
  valid: boolean; reason?: string | null; message?: string | null; list_minor: number; discount_minor: number; payable_minor: number
  /** the codes used, and the codes typed but not used with the reason (W15-R19) */
  codes?: string[]; ignored?: { code: string; why: string }[]
}
export interface PublicSquare {
  name: string
  slug: string
  theme_id: string
  domain: string
  google_login: 'requested' | 'enabled'
  has_auth_project: boolean
  /** read from the square's own database */
  database: { ok: boolean; admins?: number }
  /** the square's own auth project and its publishable key, for signing in to the square (null for squares without one) */
  auth_url: string | null
  auth_public_key: string | null
}
export interface SquareMe { email: string; name: string; role: string | null; is_admin: boolean }
export interface SignupInput { email: string; password: string; name: string; organization_name: string }
export type LogoVariant = 'light' | 'dark'
export interface SquareInput { name: string; slug: string; theme_id: string; currency?: string; phone_country?: string; modules?: string[]; launch_package?: LaunchPackageId; group_type?: string; billing_country?: string; voucher_code?: string }
/** Whether a module holds data (yes or no, never a number) and what is pending in it, as sentences to read before switching it off (W8-R27, ADR 038). */
export interface ModuleStatus { key: string; holds_data: boolean; pending: string[] }
export interface ModuleStatusAnswer { available: boolean; items: ModuleStatus[] }
/** One line of the owner's Health tab: a state and one plain sentence, never data or numbers (W10-R19, ADR 038). */
export interface HealthCheck { key: string; group: 'system' | 'jobs' | 'setup' | string; state: 'ok' | 'warn' | 'fail' | 'off' | string; text: string }
export interface SquareHealth { reachable: boolean; version: string; checks: HealthCheck[] }
/** Support access (ADR 089, W23-R67): the owner lets rootsquares staff look at the square for a while. Scopes name the parts; members are always read only. */
export type SupportScope = 'content' | 'settings' | 'health' | 'members'
export type SupportMinutes = 60 | 1440 | 10080
export interface SupportSession { id: string; staff_name: string; started_at: string; ended_at: string | null; ended_by: string | null }
export interface SupportGrant { id: string; created_at: string; expires_at: string; duration_minutes: number; scopes: SupportScope[]; allow_changes: boolean; note: string | null; sessions: SupportSession[] }
export interface SupportRequest { id: string; staff_name: string; note: string; created_at: string; answered_at: string | null }
export interface SupportAuditRow { at: string; action: string; who: string; by_you: boolean; scopes: SupportScope[]; allow_changes: boolean | null; ended_by: string | null }
export interface SupportState { grant: SupportGrant | null; requests: SupportRequest[]; can_manage: boolean }
/** Analytics (ADR 090, W23-R79): the owner's visit numbers, passed on from the square. A figure under 5 is null with its `few` flag. Nothing here is stored by the platform. */
export interface AnalyticsDay { day: string; visits: number; views: number; visitors: number }
export interface AnalyticsTotals { visits: number; views: number; visitors: number }
export interface AnalyticsPage { path: string; views: number | null; few: boolean }
export interface AnalyticsSource { source: string; visits: number | null; few: boolean }
export interface AnalyticsEvent { slug: string; title: string; views: number | null; views_few: boolean; tickets: number | null; tickets_few: boolean }
export interface Analytics {
  enabled: boolean; reachable: boolean; resting: boolean; counting: boolean; days: number; start: string | null; end: string | null
  daily: AnalyticsDay[]; totals: AnalyticsTotals; previous: AnalyticsTotals; pages: AnalyticsPage[]; sources: AnalyticsSource[]; events: AnalyticsEvent[]
}
/** One page of the log of every use, newest first (10 a page by default). */
export interface SupportActivity { items: SupportAuditRow[]; page: number; per_page: number; total: number }
export interface SupportGrantInput { duration_minutes: SupportMinutes; scopes: SupportScope[]; allow_changes: boolean; members_confirmed: boolean; note?: string }
/** An optional module a square can have; `tier` says whether it is preselected (recommended) or off until chosen (good_to_have); `needs` must be on with it. */
/** A kind of group a new square can be, with the modules that start on for it (backend/app/platform/starter_sets.py, W14-R10). */
export interface StarterSetInfo { key: string; label: string; description: string; modules: string[] }
/** The countries whose phone number rule a square can use; keep equal to SUPPORTED_PHONE_COUNTRIES in backend/app/platform/schemas.py. */
export const PHONE_COUNTRIES = ['NO', 'SE', 'DK', 'FI', 'IS', 'DE', 'GB', 'IE', 'NL', 'FR', 'US', 'CA', 'IN', 'BD'] as const
/** The currencies a square can be created with; keep equal to SUPPORTED_CURRENCIES in backend/app/platform/schemas.py. */
export const CURRENCIES = ['NOK', 'SEK', 'DKK', 'EUR', 'GBP', 'USD', 'ISK'] as const

export interface PlatformApi {
  me(): Promise<PlatformUser>
  signup(input: SignupInput): Promise<PlatformUser>
  login(email: string, password: string): Promise<PlatformUser>
  logout(): Promise<void>
  /** Onboarding for a user who signed in through the identity provider and has no organisation yet. */
  createOrganization(name: string): Promise<PlatformUser>
  listSquares(): Promise<PlatformSquare[]>
  createSquare(input: SquareInput): Promise<PlatformSquare>
  getSquare(id: string): Promise<PlatformSquare>
  /** Provision a failed square again. */
  retrySquare(id: string): Promise<PlatformSquare>
  /** Upload or replace the square's logo (PNG, JPEG or WebP, at most 1 MB). */
  uploadSquareLogo(id: string, file: File, variant?: LogoVariant): Promise<PlatformSquare>
  removeSquareLogo(id: string, variant?: LogoVariant): Promise<PlatformSquare>
  /** The optional modules a square can have. */
  listModules(): Promise<ModuleInfo[]>
  /** Modules plus the always-on parts and what each needs (the custom package form, W19-R24) */
  moduleCatalogue(): Promise<ModuleCatalogue>
  /** The kinds of group a new square can be; each decides which modules start on. */
  listStarterSets(): Promise<StarterSetInfo[]>
  /** What each module holds and has pending. `available` false = the square server could not be asked. */
  getModuleStatus(id: string): Promise<ModuleStatusAnswer>
  /** The health of the square for its owner (W10-R19): reachable, database, storage, background jobs, setup. */
  getSquareHealth(id: string): Promise<SquareHealth>
  /** Support access of a square: the active grant, the requests waiting and the log of every use (only the owner may grant or end it). */
  getSupport(id: string): Promise<SupportState>
  getSupportActivity(id: string, page: number, perPage?: number): Promise<SupportActivity>
  /** The owner's visit numbers (7, 30 or 90 days) and the owner's switch for counting (ADR 090). */
  getAnalytics(id: string, days: number): Promise<Analytics>
  setAnalytics(id: string, enabled: boolean): Promise<Analytics>
  createSupportGrant(id: string, input: SupportGrantInput): Promise<SupportGrant>
  revokeSupport(id: string): Promise<SupportState>
  /** Turn modules on or off; the server completes the list with what the chosen ones need. Nothing is deleted when one is turned off. */
  setSquareModules(id: string, modules: string[]): Promise<PlatformSquare>
  /** The prices, as data (public). */
  getPrices(): Promise<PlanPrice[]>
  /** What a code would take off a payment that does not exist yet: a launch package's first payment or a new Event pass (Create square) */
  voucherPreview(input: { code: string; kind: 'first' | 'event_pass'; launch_package?: LaunchPackageId }): Promise<VoucherCheck>
  /** What a code would take off a payment, before the owner pays (nothing is saved) */
  voucherCheck(squareId: string, input: { code: string } & CheckoutInput): Promise<VoucherCheck>
  /** Countries whose tax is inside the listed prices, as percent (W13-R51, ADR 060): the customer pays the listed price in all there. */
  getTaxRates(): Promise<Record<string, number>>
  /** Public: "Nothing fits you? Speak to us" on the Pricing page leaves a prospect for the owner console (W19-R22). `website` is a hidden field only a bot fills. */
  submitProspect(input: ProspectInput): Promise<void>
  /** Start a payment; the browser goes to `url` to pay (the test checkout page now, Stripe later). The plan changes only when payment is confirmed. */
  startCheckout(squareId: string, input: CheckoutInput): Promise<{ order_id: string; url: string }>
  getOrder(orderId: string): Promise<BillingOrder>
  listOrders(squareId: string): Promise<BillingOrder[]>
  /** ask the backend to look at the payment provider again for a pending order (W25-R27): it is applied if the provider says it was paid; the order as it is now */
  confirmOrder(squareId: string, orderId: string): Promise<BillingOrder>
  /** The invoice of a paid (or refunded) payment of the owner's square (W19-R16) */
  getInvoice(orderId: string): Promise<Invoice>
  /** Test checkout only (the fake provider): pay or cancel an order. No money moves. */
  fakeConfirm(orderId: string, outcome: 'paid' | 'cancelled'): Promise<BillingOrder>
  /** The owner of an Event pass says the reports are saved (W11, ADR 044) */
  confirmEventPassExport(squareId: string): Promise<PlatformSquare>
  /** The default billing period of the square (W10-R46). Nothing is charged by this. */
  setBillingInterval(id: string, interval: 'month' | 'year'): Promise<PlatformSquare>
  /** Stop or resume the automatic renewal (W12-R13). The paid time stays; nothing is refunded. */
  cancelRenewal(id: string): Promise<PlatformSquare>
  /** The payment provider's page for the card and receipts (W12-R17) */
  billingPortal(id: string): Promise<{ url: string }>
  resumeRenewal(id: string): Promise<PlatformSquare>
  /** Put the square to sleep (keep) or wake it (live), W10-R41. Nothing is deleted. */
  setRunningPlan(id: string, plan: 'keep' | 'live'): Promise<PlatformSquare>
  /** Live to Keep starts at the next renewal; Keep to Live starts at once and is charged for the rest of the period; Live while a downgrade waits cancels it (W18-R34) */
  changePlan(id: string, plan: 'keep' | 'live'): Promise<PlatformSquare>
  /** Change the square's theme (W9-R5). Only the look changes; content, modules and data stay. */
  setSquareTheme(id: string, themeId: string): Promise<PlatformSquare>
  /** the owner's e-mail contact for the square (ADR 093); null or blank clears it */
  setMailContact(id: string, email: string | null): Promise<PlatformSquare>
  /** the square's own sending domain (Grove, ADR 091 and 095): read it; the owner asks for it, staff set it up; the owner checks it, changes the name, removes it,
   *  sends the records to a web person or asks for IT help */
  getSiteDomain(id: string): Promise<SiteDomain>
  requestSiteDomain(id: string, domain: string): Promise<SiteDomain>
  withdrawSiteDomainRequest(id: string): Promise<SiteDomain>
  checkSiteDomain(id: string): Promise<SiteDomain>
  askSiteDomainHelp(id: string): Promise<SiteDomain>
  removeSiteDomain(id: string): Promise<SiteDomain>
  getMailDomain(id: string): Promise<MailDomain>
  requestMailDomain(id: string, input: { domain: string; local_part: string }): Promise<MailDomain>
  withdrawMailDomainRequest(id: string): Promise<MailDomain>
  setMailFromName(id: string, localPart: string): Promise<MailDomain>
  checkMailDomain(id: string): Promise<MailDomain>
  removeMailDomain(id: string): Promise<MailDomain>
  sendMailDomainInstructions(id: string, to: string): Promise<MailDomain>
  askMailDomainHelp(id: string): Promise<MailDomain>
  /** What waits for the person as owner of squares: the strip on the dashboards and the count in the side bar (W25-R35). */
  getAttention(): Promise<PortalAttentionList>
  /** Save the owner's own colours and font pair on top of the theme, or clear them with null (W18-R18). Square package and above; otherwise 403 package_required. */
  setSquareLook(id: string, look: ThemeLook | null): Promise<PlatformSquare>
  /** Save the draft look and get its link's token (W18-R47). passcode: undefined keeps the old one, '' removes it; renew starts a new link. */
  saveLookDraft(id: string, look: ThemeLook, options?: { passcode?: string; renew?: boolean; themeId?: string }): Promise<PlatformSquare>
  /** Save the whole list of seasonal looks (W18-R49); an empty list removes them. Items without an id get one. */
  saveLookSeasons(id: string, seasons: Array<Omit<LookSeason, 'id'> & { id?: string }>): Promise<PlatformSquare>
  /** Take the draft down: its link stops working. */
  removeLookDraft(id: string): Promise<PlatformSquare>
  /** The draft goes live and the link is gone. */
  publishLookDraft(id: string): Promise<PlatformSquare>
  /** Public hello-world data of a ready square (no sign-in). 404 when it does not exist or is not ready. */
  getPublicSquare(slug: string): Promise<PublicSquare>
  /** The square served on this host name (its domain, or <slug>.localhost while developing). 404 when there is none. */
  getPublicSquareByHost(host: string): Promise<PublicSquare>
  /** Who the token of the square's own auth project belongs to, and their role in the square. */
  getSquareMe(slug: string, squareToken: string): Promise<SquareMe>
  /** Delete a square for good (its project at the provider too). The address is typed to confirm; force is for platform admins. */
  deleteSquare(id: string, confirmSlug: string, force?: boolean): Promise<void>
  /** Everything the platform holds about the signed-in person, as a JSON file. */
  exportMyData(): Promise<Blob>
  /** Delete the signed-in person's account. false = their sign-in account at the identity provider could not be removed automatically. */
  deleteAccount(confirmEmail: string): Promise<boolean>

}
