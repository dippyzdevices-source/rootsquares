/**
 * What it is:   The owner's own fonts on top of the font pair (rootsquares W25-R63): a heading font, a body font (any family of Google Fonts) and the accent lines ("Come as you are" above a title).
 * What it does: cleanType() checks what a message or the platform sends (a family name of letters, digits and spaces, a known category, weights 100 to 900); typeUrl() builds the one Google Fonts
 *               address that loads the chosen families; faceStack() builds the font-family value with a fallback by category; ACCENTS is the short list of accent fonts.
 *               The platform's server has already checked the family against the Google list and stored its category and weights, so this app needs no catalogue; the strict check here is
 *               a second line of defence, because the values end up in CSS and in an address.
 * How to use:   cleanType({ display: { f: 'Lora', c: 'serif', w: [400, 700] }, accent: 'dancing' }); typeUrl(type); applyThemeOverrides.ts writes the CSS.
 * Run:          from square/frontend: npx vitest run src/themes/customFonts.spec.ts
 * Read before:  src/themes/fontPairs.ts, backend/app/platform/theme_overrides.py (ACCENT_IDS and the face rules, kept equal by a test).
 * Read after:   src/themes/applyThemeOverrides.ts.
 */

export interface Face { f: string; c: string; w: number[] }
export interface TypeChoice { display?: Face | null; body?: Face | null; accent?: string | null }

/** The accent fonts (the handwritten line over a title). Keep the ids equal to ACCENT_IDS of backend/app/platform/theme_overrides.py ("headings" is no font of its own: the accent lines use the heading font). */
export const ACCENTS: Record<string, { family: string; q: string }> = {
  sacramento: { family: 'Sacramento', q: 'family=Sacramento' },
  dancing: { family: 'Dancing Script', q: 'family=Dancing+Script:wght@400;700' },
  caveat: { family: 'Caveat', q: 'family=Caveat:wght@400;700' },
  'great-vibes': { family: 'Great Vibes', q: 'family=Great+Vibes' },
}
export const ACCENT_IDS = [...Object.keys(ACCENTS), 'headings']

const NAME = /^[A-Za-z0-9][A-Za-z0-9 ]{0,60}$/
const CATEGORIES = ['serif', 'sans-serif', 'display', 'handwriting', 'monospace']
const FALLBACK: Record<string, string> = {
  serif: 'Georgia,serif',
  'sans-serif': '"Helvetica Neue",Arial,sans-serif',
  display: '"Helvetica Neue",Arial,sans-serif',
  handwriting: 'cursive',
  monospace: 'ui-monospace,Menlo,Consolas,monospace',
}

function cleanFace(v: unknown): Face | null {
  const o = v as { f?: unknown; c?: unknown; w?: unknown } | null | undefined
  if (!o || typeof o !== 'object' || typeof o.f !== 'string' || !NAME.test(o.f) || typeof o.c !== 'string' || !CATEGORIES.includes(o.c)) return null
  const w = Array.isArray(o.w) ? [...new Set(o.w.filter((x): x is number => Number.isInteger(x) && x >= 100 && x <= 900 && x % 100 === 0))].sort((a, b) => a - b).slice(0, 4) : []
  return { f: o.f, c: o.c, w: w.length ? w : [400] }
}

/** Only what is valid; null when nothing is left. */
export function cleanType(v: unknown): TypeChoice | null {
  const o = v as { display?: unknown; body?: unknown; accent?: unknown } | null | undefined
  if (!o || typeof o !== 'object') return null
  const out: TypeChoice = {}
  const display = cleanFace(o.display)
  const body = cleanFace(o.body)
  if (display) out.display = display
  if (body) out.body = body
  if (typeof o.accent === 'string' && ACCENT_IDS.includes(o.accent)) out.accent = o.accent
  return Object.keys(out).length ? out : null
}

export const faceStack = (face: Face): string => `"${face.f}",${FALLBACK[face.c]}`

/** The one address that loads every chosen family (heading, body, a chosen accent font); null when nothing needs loading. */
export function typeUrl(t: TypeChoice | null | undefined): string | null {
  if (!t) return null
  const parts: string[] = []
  for (const face of [t.display, t.body]) if (face) parts.push(`family=${face.f.replace(/ /g, '+')}:wght@${face.w.join(';')}`)
  if (t.accent && ACCENTS[t.accent]) parts.push(ACCENTS[t.accent]!.q)
  const seen = new Set<string>()
  const unique = parts.filter((p) => (seen.has(p) ? false : (seen.add(p), true)))
  return unique.length ? `https://fonts.googleapis.com/css2?${unique.join('&')}&display=swap` : null
}

/** The accent lines' font-family value, or null to leave the theme's own (Sacramento). "headings" follows the heading font. */
export function accentStack(t: TypeChoice | null | undefined): string | null {
  if (!t?.accent) return null
  if (t.accent === 'headings') return 'var(--ds-font-display)'
  const a = ACCENTS[t.accent]
  return a ? `"${a.family}",cursive` : null
}
