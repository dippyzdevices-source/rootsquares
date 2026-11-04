// Types, constants and the ApiError class of the platform API that both applications use (ADR 084 stage 3d). Customer-only types stay in the customer app (src/services/platformTypes.ts), admin-only types in the admin application (src/admin/adminTypes.ts).

export type SquareStatus = 'provisioning' | 'ready' | 'failed'
/** A price as data (W10-R42): integer minor units (cents) and a currency; `interval` one_off, month or year. */
export interface PlanPrice { key: string; amount_minor: number; currency: string; interval: 'one_off' | 'month' | 'year' }
/** A payment the owner started: an upgrade of the launch package (the difference) or a running period. */
export interface BillingOrder {
  id: string; square_id: string; kind: 'upgrade' | 'running' | 'event_upgrade' | 'event_pass' | 'first'; launch_package: LaunchPackageId | null; running_plan: 'live' | 'keep' | null; interval: 'month' | 'year' | null
  amount_minor: number; currency: string; status: 'pending' | 'paid' | 'cancelled' | 'failed' | 'refunded'; provider: string; created_at: string; paid_at: string | null; refunded_minor?: number
  /** The card that paid, for the history (Stripe only): brand and last four digits */
  card_brand?: string | null; card_last4?: string | null
  /** A voucher lowered this payment (W14-R27): `list_minor` is the price before it, `amount_minor` what was charged */
  list_minor?: number | null; discount_minor?: number; voucher_code?: string | null
}
/** A person who asked to speak to us about a custom package (W19-R22) */
export interface Prospect { id: string; name: string; email: string; phone: string; message: string | null; source: string; status: 'new' | 'contacted' | 'won' | 'closed'; notes: string | null; created_at: string; updated_at: string }
/** Who issues the invoices (W19-R16): platform settings; an empty value is not shown on the invoice */
export interface InvoiceSeller { name: string; org_no: string; address: string; email: string; prefix: string; footer: string }
export type LaunchPackageId = 'roots' | 'square' | 'grove' | 'event'
export interface VoucherInput {
  code: string; kind: 'percent' | 'fixed'; value: number; applies_to: 'all' | 'launch' | 'event_pass'; packages: LaunchPackageId[] | null
  valid_from: string | null; valid_until: string | null; max_uses: number | null; once_per_org: boolean; new_customers_only: boolean; active: boolean; stackable: boolean
  partner_id: string | null; note: string | null
}
export interface PlatformVoucher extends VoucherInput { id: string; created_at: string; partner_name: string | null; uses: number; discount_minor: number }
/** The life of an Event pass (W11, ADR 044): live, then a read-only archive, then it leaves service and is deleted for good */
export interface EventPassInfo {
  phase: 'live' | 'archive' | 'removed'
  started_at: string | null
  live_until: string | null
  archive_until: string | null
  purge_at: string | null
  /** Days until the next change */
  days_left: number
  /** When the owner said the reports are saved (a plain yes) */
  export_confirmed_at: string | null
  reminders_sent: number[]
}
/** The owner's own colours and font pair on top of a theme (W18-R18): three colours (page, text, accent) and a font pair id; a null part means the theme as designed. */
export interface ThemeLook { colors: { bg: string; ink: string; acc: string } | null; colors_dark?: { bg: string; ink: string; acc: string } | null; fonts: string | null; spinners?: string[] | null; shape?: Partial<Record<'buttons' | 'cards' | 'photos' | 'edges', string>> | null; feel?: Partial<Record<'mode' | 'switch' | 'density' | 'text' | 'motion' | 'divider', string>> | null; type?: { display?: { f: string; c: string; w: number[] } | null; body?: { f: string; c: string; w: number[] } | null; accent?: string | null } | null }

/** The look the owner shares by a link before it goes live (W18-R47). Owner only; the token makes the link. */
export interface LookDraft { look: Partial<ThemeLook>; theme_id?: string | null; token: string; expires_at: string; expired: boolean; has_passcode: boolean }

/** A seasonal look (W18-R49): the public site wears its look (and theme) between start and end (YYYY-MM-DD, UTC); a yearly one repeats and may cross the new year. */
export interface LookSeason { id: string; name: string; start: string; end: string; yearly: boolean; theme_id?: string | null; look: Partial<ThemeLook> }

/** The square's own website domain (ADR 098, Grove): the owner points a CNAME at `target`; staff add the domain on the host and activate it. `dns` is filled only by a check. */
export interface SiteDomain {
  allowed: boolean
  target: string
  /** none | requested (waiting for staff) | active (the square is served on the own domain) */
  state: 'none' | 'requested' | 'active'
  domain: string | null
  requested_domain: string | null
  requested_at: string | null
  /** the square's address on rootsquares, which keeps working */
  default_domain: string
  /** the owner asked staff for IT help with the domain (a small one-time support fee applies) */
  help_requested: boolean
  dns: 'unchecked' | 'pointing' | 'not_pointing' | 'unknown'
  /** the domain at the host (Render), asked only by the staff API: off (no key, staff add it by hand) | not_added | unverified | verified | unknown */
  render: 'off' | 'not_added' | 'unverified' | 'verified' | 'unknown'
}

/** One DNS record the owner adds for the square's own sending domain (ADR 091); `name` is relative to the domain the owner typed, as Resend gives it. */
export interface MailDomainRecord { record: string; type: string; name: string; value: string; priority: number | null; status: string }
/** The square's own sending domain (Grove): what the owner typed, Resend's status and the records to add. `from_address` is set only while it is verified. */
export interface MailDomain {
  allowed: boolean
  available: boolean
  domain: string | null
  local_part: string
  status: string | null
  verified: boolean
  from_address: string | null
  records: MailDomainRecord[]
  /** none | requested (the owner asked, staff have not set it up) | registered (set up, waiting for the DNS records) | verified (in use) */
  state: 'none' | 'requested' | 'registered' | 'verified'
  requested_domain: string | null
  requested_local: string | null
  requested_at: string | null
  /** the owner asked staff for IT help (a small one-time support fee applies) */
  help_requested: boolean
  /** a request is set up at once (MAIL_DOMAIN_AUTO_APPROVE); false = staff set it up in the admin application */
  auto_approve: boolean
}

export interface PlatformSquare {
  id: string
  org_id: string
  /** the organisation's name (W26-R27): the dashboard groups the squares by it */
  org_name?: string
  name: string
  slug: string
  theme_id: string
  /** The owner's own look on top of the theme (Square package and above, W18-R18), or null */
  theme_overrides?: Partial<ThemeLook> | null
  /** The seasonal looks (W18-R49) */
  look_seasons?: LookSeason[]
  /** The shared draft look, or null (W18-R47) */
  look_draft?: LookDraft | null
  /** ISO 4217 code chosen when the square was created (default NOK) */
  currency: string
  /** ISO 3166 alpha-2 code chosen when the square was created (default NO): the phone number rule of its forms */
  phone_country: string
  /** The organisation's country (ISO alpha-2) for tax and invoices, or null (W13-R43) */
  billing_country?: string | null
  /** The code given when the square was created; it lowers the first payment (W14-R30) */
  voucher_code?: string | null
  /** The tax percent inside the listed prices for that country (0 = none) (W13-R51) */
  tax_percent?: number
  /** The square's own domain once custom domains are built (MISSING.md: domain automation); not sent yet, so always empty */
  custom_domain?: string | null
  /** The optional modules that are on (docs/reference/optional-modules.md); the owner changes them on the square's page */
  modules: string[]
  /** The running plan is paid up to here (W10-R42), or null */
  paid_until?: string | null
  /** Only for an Event pass (W11, ADR 044) */
  event_pass?: EventPassInfo | null
  /** A new Event pass not yet paid: not built, no clock (W12-R6) */
  awaiting_payment?: boolean
  /** A launch package in its trial (or past it) whose first payment is not made (W12-R9) */
  first_payment_due?: boolean
  /** Real money is on: while the first payment is due, upgrades and running periods wait for it (W12-R16) */
  payment_required?: boolean
  /** A payment customer exists: the card and receipts page can be opened (W12-R17) */
  can_manage_billing?: boolean
  /** The last renewal payment failed: until grace_ends the site stays live, then it sleeps (W12-R18) */
  payment_failed?: boolean
  grace_ends?: string | null
  /** renewing = renews by itself; ending = cancelled, runs until paid_until (W12-R13) */
  subscription?: 'renewing' | 'ending' | null
  /** keep = a downgrade that starts when the paid time ends (paid_until); null = none (W18-R34) */
  pending_plan?: 'keep' | null
  /** awake | sleeping | waking | failed (W10-R44): while it sleeps its project is paused and nobody can sign in to it */
  sleep_state?: 'awake' | 'sleeping' | 'waking' | 'failed'
  /** where the square's contact-form messages and payment notices go and where replies to its customer mails go (ADR 093); null = its public contact address */
  mail_contact_email?: string | null
  /** Its project was deleted after 12 months asleep with nothing paid (W13-R48, ADR 059): it cannot be woken */
  archived_at?: string | null
  /** The owner's default billing period, what the plan cards offer first (W10-R46) */
  billing_interval?: 'month' | 'year'
  /** The launch package (W10-R40): decides which optional modules the owner may switch on; squares made before packages are 'grove' */
  launch_package: LaunchPackageId | 'custom'
  /** A custom package (W19-R20, ADR 082): the one amount agreed per period (USD minor units) and its period; null for every other package */
  custom_amount_minor?: number | null
  custom_interval?: 'month' | 'year' | null
  /** The kind of group (cultural | religious, W14-R10); null for an Event pass or a square made before starter sets */
  group_type?: string | null
  /** live | keep | event */
  running_plan: 'live' | 'keep' | 'event'
  /** The optional modules the launch package lets the owner switch on */
  allowed_modules: string[]
  /** The always-on parts this square has: all of them, except in a custom package that leaves some out (W19-R24) */
  core_modules?: string[]
  /** Public address of the square's logo, or null (the site then shows a letter mark) */
  logo_url: string | null
  /** Public address of the logo for dark backgrounds (footer, dark mode), or null (the light logo is used) */
  logo_dark_url: string | null
  status: SquareStatus
  domain: string
  url: string
  has_database: boolean
  error: string | null
  created_at: string
  /** Google sign-in of the square: a platform admin switches it on by hand (needs its callback URL added in Google Cloud Console) */
  google_login: 'requested' | 'enabled'
  auth_callback_url: string | null
}
/** An always-on part (Home, About, Sign-in, Admin ...) and the parts it needs; only a custom package can leave one out (W19-R24) */
export interface CorePart { key: string; label: string; description: string; needs: string[] }
export interface ModuleCatalogue { items: ModuleInfo[]; core: CorePart[]; module_core_needs: Record<string, string[]> }
export interface ModuleInfo { key: string; label: string; description: string; tier: 'recommended' | 'good_to_have'; needs: string[]; parent?: string | null; starts_off?: boolean }
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public errors: { loc: (string | number)[]; msg: string }[] = [],
    public extra: Record<string, unknown> = {},
  ) {
    super(message)
  }
}

