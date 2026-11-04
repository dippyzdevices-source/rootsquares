/**
 * What it is:   The "Feel" choices of the owner's own look: the default light or dark, whether the visitor's light/dark switch is shown, the density of the page, the text size, the kind of motion and the style of the divider ornaments
 *               (rootsquares W18, W18-R44, built after the shapes of docs/plans/themes-shapes-plan.md).
 * What it does: Lists the named options per part as data; feelCss() builds the CSS of density, motion and a hidden switch; feelMode() says which of light or dark a visitor starts in.
 *               Density sets the section spacing (`--ds-section-y`, `--ds-space-5..9` and `.lt-sec`); motion calm stops the scrolling tickers and the hover lift of cards and photos,
 *               motion nolift stops only the hover lift, nostrip only the scrolling strips (W25-R57; `none` of earlier looks is read as calm). Text size zooms the public page (112 % or 125 %, text and the space around it);
 *               the divider `line` hides the glyph of the motif lines (`.ds-motif`), `none` hides the whole motif; the layout themes draw no motif of their own. The admin and member console keeps its own spacing and its own switch.
 *               `!important` is used for `.lt-sec` and for motion because themes set them per theme.
 * How to use:   feelCss({ density: 'airy', motion: 'calm', switch: 'hide' }); feelMode({ mode: 'dark' }, stored, systemDark) -> 'dark' | 'light' | null (null = the usual rule);
 *               parseFeel('mode:dark,density:airy') reads the `?feel=` preview text. Ids are kept equal to backend/app/platform/theme_overrides.py (FEEL_OPTIONS) by a test.
 * Run:          from square/frontend: npx vitest run src/themes/feel.spec.ts
 * Read before:  src/themes/shapes.ts (the same pattern), src/composables/useTheme.ts (where feelMode is used).
 * Read after:   docs/plans/themes-shapes-plan.md (the owner's choice of 2026-10-22 to build mode, density and motion as the Feel tab).
 */

export interface FeelChoice { mode?: string | null; switch?: string | null; density?: string | null; text?: string | null; motion?: string | null; divider?: string | null }

/** Where a visitor starts: light, dark, or the device setting. The visitor's own choice with the switch (when shown) wins. */
export const FEEL_OPTIONS: Record<'mode' | 'switch' | 'density' | 'text' | 'motion' | 'divider', string[]> = {
  mode: ['light', 'dark', 'system'],
  switch: ['show', 'hide'],
  density: ['compact', 'comfortable', 'airy'],
  text: ['normal', 'large', 'xlarge'],
  motion: ['lively', 'nolift', 'nostrip', 'calm'],
  divider: ['glyph', 'line', 'none'],
}
const PARTS = ['mode', 'switch', 'density', 'text', 'motion', 'divider'] as const

/** Only the options that exist (a part that is not chosen is left out). Null when nothing valid is left. */
export function cleanFeel(f: FeelChoice | null | undefined): FeelChoice | null {
  if (!f || typeof f !== 'object') return null
  const out: FeelChoice = {}
  for (const p of PARTS) {
    const v = f[p]
    if (p === 'motion' && v === 'none') out[p] = 'calm' // the old option, stopping everything, is the calm one now (W25-R57)
    else if (typeof v === 'string' && FEEL_OPTIONS[p].includes(v)) out[p] = v
  }
  return Object.keys(out).length ? out : null
}

/** Section spacing per density: the design system's section and space tokens, and the layout-theme section padding (desktop, phone). */
const DENSITY: Record<string, { y: string; sp: [string, string, string, string, string]; lt: [string, string] }> = {
  compact: { y: '56px', sp: ['18px', '24px', '34px', '44px', '56px'], lt: ['52px', '36px'] },
  comfortable: { y: '96px', sp: ['24px', '32px', '48px', '64px', '96px'], lt: ['84px', '56px'] },
  airy: { y: '132px', sp: ['32px', '44px', '64px', '88px', '132px'], lt: ['120px', '76px'] },
}
/** Text size: the public page is enlarged like a browser zoom (text and the space around it), so layout-theme text that is written in pixels follows too. */
const TEXT_ZOOM: Record<string, string> = { normal: '1', large: '1.12', xlarge: '1.25' }
const SCOPE = 'html:root .ds-scope.ds-scope'
const PUBLIC_LT = `${SCOPE} .lt-sec`

const CARD_HOVER = ['.ds-card', '.lt-card', '.lt-rail-card', '.lt-pe-card', '.lt-sg-card', '.lt-pr-card', '.lt-co-card', '.lt-photo', '.ds-rect-inner', '.ds-btn', '.lt-btn']

/** The CSS of the density, motion and switch choices, or '' when none was made (mode is not CSS: see feelMode). */
export function feelCss(f: FeelChoice | null | undefined): string {
  const c = cleanFeel(f)
  if (!c) return ''
  const out: string[] = []
  if (c.density) {
    const d = DENSITY[c.density]
    out.push(`${SCOPE}{--ds-section-y:${d.y};--ds-space-5:${d.sp[0]};--ds-space-6:${d.sp[1]};--ds-space-7:${d.sp[2]};--ds-space-8:${d.sp[3]};--ds-space-9:${d.sp[4]};}`)
    // the console keeps the design system's own spacing
    const base = DENSITY.comfortable
    out.push(`html:root .ds-appshell.ds-appshell{--ds-space-5:${base.sp[0]};--ds-space-6:${base.sp[1]};--ds-space-7:${base.sp[2]};--ds-space-8:${base.sp[3]};--ds-space-9:${base.sp[4]};}`)
    out.push(`${PUBLIC_LT}:not(:first-child){padding-top:${d.lt[0]} !important;}`)
    out.push(`${PUBLIC_LT}{padding-bottom:${d.lt[0]} !important;}`)
    out.push(`@media (max-width:720px){${SCOPE}{--ds-section-y:var(--ds-space-7);}${PUBLIC_LT}:not(:first-child){padding-top:${d.lt[1]} !important;}${PUBLIC_LT}{padding-bottom:${d.lt[1]} !important;}}`)
  }
  if (c.text) {
    // the outermost scope of a public page only (not a scope inside a scope, which would enlarge twice), and not the console
    out.push(`html:root .ds-scope:not(.ds-scope .ds-scope):not(:has(.ds-appshell)){zoom:${TEXT_ZOOM[c.text]};}`)
  }
  if (c.divider === 'line') out.push(`${SCOPE} .ds-motif-glyph:not(.ds-appshell .ds-motif-glyph){display:none !important;}`)
  if (c.divider === 'none') out.push(`${SCOPE} .ds-motif:not(.ds-appshell .ds-motif){display:none !important;}`)
  if (c.motion === 'calm' || c.motion === 'nostrip') out.push(`${SCOPE} .lt-ticker-track,${SCOPE} .sponsors-track{animation-play-state:paused !important;}`)
  if (c.motion === 'calm' || c.motion === 'nolift') out.push(`${CARD_HOVER.map((s) => `${SCOPE} ${s}:hover`).join(',')}{transform:none !important;}`)
  if (c.switch === 'hide') {
    out.push(`html:root .ds-scope .ds-theme-toggle:not(.ds-appshell .ds-theme-toggle),html:root .lt-mode:not(.ds-appshell .lt-mode){display:none !important;}`)
  }
  return out.join('\n')
}

/**
 * The mode a visitor starts in, or null for the usual rule (the stored choice, then the theme's own default). With the switch shown the visitor's stored choice wins over the
 * owner's default; with the switch hidden the owner's default is the only choice. `system` follows the device setting.
 */
export function feelMode(f: FeelChoice | null | undefined, stored: 'light' | 'dark' | null, systemDark: boolean): 'light' | 'dark' | null {
  const c = cleanFeel(f)
  if (!c?.mode) return null
  if (stored && c.switch !== 'hide') return stored
  return c.mode === 'system' ? (systemDark ? 'dark' : 'light') : (c.mode as 'light' | 'dark')
}

/** `mode:dark,density:airy` (the `?feel=` preview) to a choice; null when nothing valid is in it. */
export function parseFeel(v: string | null | undefined): FeelChoice | null {
  if (!v) return null
  const o: Record<string, string> = {}
  for (const part of v.split(',')) {
    const [k, val] = part.split(':').map((x) => x.trim())
    if ((PARTS as readonly string[]).includes(k) && val) o[k] = val
  }
  return cleanFeel(o)
}

/** The choice as the `?feel=` text (for the kept preview). */
export function feelText(f: FeelChoice | null | undefined): string {
  const c = cleanFeel(f)
  return c ? PARTS.filter((p) => c[p]).map((p) => `${p}:${c[p]}`).join(',') : ''
}
