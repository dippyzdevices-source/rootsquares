// Which square is this site? (rootsquares change W6-R36; not in bca-oslo.)
// One server serves many squares and finds the square by the host name, so the browser asks it: GET /api/square/config gives the square's name,
// slug, theme and its own sign-in project (project url and publishable key, both public by design). Asked once, before the app starts (top-level
// await). The test suite never asks (MODE 'test'), and a single-tenant server has no such answer: both fall back to the bca-oslo values below.
import { demoActive } from '../demo/install'
import { openDraftLook } from '../themes/draftLook'

export interface SquareAuthConfig {
  provider?: string
  url?: string
  public_key?: string
}

/** How phone numbers are written and checked in this square (W6-R52); the same rule the backend uses. */
export interface PhoneRule {
  country: string
  name: string
  dial: string
  min_digits: number
  max_digits: number
  trunk_zero: boolean
}

const NORWAY: PhoneRule = { country: 'NO', name: 'Norway', dial: '47', min_digits: 8, max_digits: 8, trunk_zero: false } // bca-oslo's own rule

interface SquareConfigAnswer {
  slug?: string
  name?: string
  theme_id?: string
  theme_overrides?: { colors?: { bg: string; ink: string; acc: string } | null; colors_dark?: { bg: string; ink: string; acc: string } | null; fonts?: string | null; spinners?: string[] | null; shape?: { buttons?: string | null; cards?: string | null; photos?: string | null; edges?: string | null } | null; feel?: { mode?: string | null; switch?: string | null; density?: string | null; text?: string | null; motion?: string | null; divider?: string | null } | null; type?: { display?: { f: string; c: string; w: number[] } | null; body?: { f: string; c: string; w: number[] } | null; accent?: string | null } | null } | null
  currency?: string
  phone?: PhoneRule
  logo_url?: string
  logo_dark_url?: string
  modules?: string[]
  /** The always-on parts a custom package leaves out (W19-R24); absent = none */
  core_off?: string[]
  features?: string[]
  /** The platform's public address, where the owner changes the package (W26-R17); absent or '' = no link */
  platform_url?: string
  /** The square sends its mail from its own verified sending domain (W26-R18); absent = unknown, nothing is warned about */
  own_mail_domain?: boolean
  group_type?: string
  sleeping?: boolean
  analytics?: boolean
  google_login?: boolean
  event_pass?: { phase?: string; live_until?: string; archive_until?: string } | null
  sleep_contact?: { contact_email?: string; contact_phone?: string; contact_address?: string }
  auth?: SquareAuthConfig
}

// The name used when no square answers (bca-oslo single-tenant mode and the tests). A served square always has its own name.
export const FALLBACK_SQUARE_NAME = 'BCA Oslo'

async function loadSquareConfig(): Promise<SquareConfigAnswer | null> {
  if (import.meta.env.MODE === 'test') return null
  try {
    const response = await fetch(`${(import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''}/api/square/config`)
    return response.ok ? ((await response.json()) as SquareConfigAnswer) : null
  } catch {
    return null
  }
}

/**
 * Development (npm run dev) and demo mode (W10-R14, any build): ?theme=<id> shows the square in another theme without changing it, ?theme=default goes back
 * to the square's own (W9-R5). The choice is kept for the browser tab, so every page of the visit follows it. A real square in a production build ignores it.
 */
function previewTheme(): string | null {
  if (import.meta.env.MODE === 'test' || typeof window === 'undefined' || !(import.meta.env.DEV || demoActive())) return null
  try {
    const asked = new URLSearchParams(window.location.search).get('theme')
    if (asked === 'default') window.sessionStorage.removeItem('rs-preview-theme')
    else if (asked) window.sessionStorage.setItem('rs-preview-theme', asked)
    return window.sessionStorage.getItem('rs-preview-theme')
  } catch {
    return null // storage blocked: the square's own theme
  }
}

const ALL_MODULES = ['events', 'payments', 'tickets', 'coupons', 'checkin', 'members', 'memberships', 'volunteering', 'accounting', 'gallery', 'news', 'magazines', 'newsletter', 'testimonials', 'sponsors', 'committee', 'founders', 'donations', 'messages']
const ALL_FEATURES = ['message_reminders', 'repeating_events']
const answer = await loadSquareConfig()
// The owner's shared draft (?look=<token>, W18-R47): for a visitor who holds the link it replaces the live theme and own look on this tab only.
let draft: Awaited<ReturnType<typeof openDraftLook>> = null
if (import.meta.env.MODE !== 'test' && typeof window !== 'undefined') {
  try { draft = await openDraftLook(window.location.search, window.sessionStorage, document, fetch, (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '') } catch { /* no draft: the live site */ }
}

export const squareProfile = {
  name: answer?.name?.trim() || FALLBACK_SQUARE_NAME,
  slug: answer?.slug ?? '',
  themeId: previewTheme() ?? draft?.themeId ?? answer?.theme_id ?? '',
  /** The owner's own colours and font pair on top of the theme (W18-R18), or null: the theme as designed. The values are checked again where they are applied (themes/applyThemeOverrides.ts). */
  themeOverrides: draft ? draft.look : (answer?.theme_overrides ?? null),
  /** ISO 4217 code chosen when the square was created (default NOK); every amount on the site is written in it. */
  currency: answer?.currency ?? 'NOK',
  /** The phone number rule chosen when the square was created (default Norway). */
  phone: answer?.phone ?? NORWAY,
  /** The square's uploaded logo (a web address), or '' (the site then shows a letter mark; W6-R53). */
  logoUrl: answer?.logo_url ?? '',
  /** The logo for dark backgrounds (footer, dark mode), or '' (the light logo is used; W6-R65). */
  logoDarkUrl: answer?.logo_dark_url ?? '',
  /** The optional modules the owner turned on (W8-R9). Without an answer every module is on, so this holds the full list; see services/modules.ts. */
  modules: answer?.modules ?? ALL_MODULES,
  /** The always-on parts this square does not have (a custom package only, W19-R24). See services/modules.ts. */
  coreOff: answer?.core_off ?? ([] as string[]),
  /** The gated features this square's package includes (W14-R25); without an answer every feature is on. See services/features.ts. */
  features: answer?.features ?? ALL_FEATURES,
  /** Where a locked feature sends the owner to change the package (W26-R17); '' = no link is shown. */
  platformUrl: answer?.platform_url ?? '',
  /** True when the own sending domain is verified (a newsletter may go out); an older server that does not say counts as true so nothing is warned about. */
  ownMailDomain: answer?.own_mail_domain ?? true,
  /** The kind of group chosen when the square was created (cultural | religious, W14-R10), or '' for a square made before starter sets. */
  groupType: answer?.group_type ?? '',
  /** The square sleeps (Keep, W10-R41, W10-R44): a true sleep, its project may be paused. Every page is the back-soon page with the copied contact details. */
  sleeping: answer?.sleeping === true,
  /** The owner switched visit counting on (ADR 090, W23-R78): only then does the site send its visit beacon. */
  analytics: answer?.analytics === true,
  /** Google sign-in is switched on in this square's sign-in project (W23-R86). Absent (a single-tenant server, an older platform) means yes, as before. */
  googleLogin: answer?.google_login !== false,
  /** An Event pass (W11, ADR 044): 'live', or 'archive' (the event is over, the owner can only read and download), with the dates; null for every other square. */
  eventPass: answer?.event_pass
    ? { phase: (answer.event_pass.phase === 'archive' ? 'archive' : 'live') as 'live' | 'archive', liveUntil: answer.event_pass.live_until ?? '', archiveUntil: answer.event_pass.archive_until ?? '' }
    : null,
  /** The public contact details the platform copied when the square went to sleep (its project is paused, so nothing can be read from it). */
  sleepContact: { email: answer?.sleep_contact?.contact_email ?? '', phone: answer?.sleep_contact?.contact_phone ?? '', address: answer?.sleep_contact?.contact_address ?? '' },
}

export const squareAuth: SquareAuthConfig | null = answer?.auth ?? null
