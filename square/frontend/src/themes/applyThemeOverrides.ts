/**
 * What it is:   Puts an owner's own colours and font pair on top of the square's theme (rootsquares W18, docs/plans/themes-dynamic-plan.md, steps 1 and 3).
 * What it does: themeOverrideCss() builds CSS rules that replace the theme's colour tokens (`--t-*`, the Tailwind bridge `--color-*` and the panel
 *               colours `--lt-*`) for light, dark and forced-dark, and its font tokens (`--t-font-*`, `--font-sans`); applyThemeOverrides() writes them into
 *               one <style id="rs-theme-overrides"> in <head> and loads the font pair's stylesheet. Admin and member pages keep the fixed fonts
 *               (src/styles/admin-type.css). Button and card corners come from themes/shapes.ts (W18 shapes step 2); structure is not touched. paper-brick is covered by the shape rule only.
 *               In development and in demo mode, `?colors=<bg>,<ink>,<accent>` (hex, e.g. ?colors=f6f1e7,2b2a28,c2410c), `?shape=buttons:pill,cards:soft`, `?feel=mode:dark,density:airy,motion:calm` and `?fonts=<pair id>`
 *               (ids in src/themes/fontPairs.ts) preview it; `?colors=off` and `?fonts=off` remove them. The choice is kept for the browser tab.
 * How to use:   applyThemeOverrides({ colors: { bg: '#f6f1e7', ink: '#2b2a28', acc: '#c2410c' }, fonts: 'soft' }); applyThemeOverrides(null) removes it.
 * Run:          from square/frontend: npx vitest run src/themes/applyThemeOverrides.spec.ts; in the browser: http://<slug>.localhost:5274/?theme=<id>&colors=...&fonts=...
 * Read before:  src/themes/deriveTokens.ts, src/themes/fontPairs.ts; the selectors of src/styles/square-layout-themes.css (generated).
 * Read after:   the next steps of docs/plans/themes-dynamic-plan.md (backend, platform Theme page).
 */
import { contrastRatio, deriveColourTokens, isHex, mix, paletteFromSeeds, type Mode, type Palette, type Seeds, type TokenMap } from './deriveTokens'
import { fontPairById, fontStack, type FontPair } from './fontPairs'
import { cleanFeel, feelCss, feelText, parseFeel, type FeelChoice } from './feel'
import { cleanShape, parseShape, shapeCss, shapeText, type ShapeChoice } from './shapes'
import { accentStack, cleanType, faceStack, typeUrl, type TypeChoice } from './customFonts'

const STYLE_ID = 'rs-theme-overrides'
const KEY = 'rs-preview-colors'
const FONT_KEY = 'rs-preview-fonts'
const SHAPE_KEY = 'rs-preview-shape'
const FEEL_KEY = 'rs-preview-feel'
const DARK_KEY = 'rs-preview-dcolors'
const LINK_ATTR = 'data-rs-font-pair'
const CUSTOM_LINK_ATTR = 'data-rs-font-custom'
/** paper-brick has no theme id: with the owner's own colours the colour rules apply to it through a marker on <html> (`data-own-colours`, set by applyThemeOverrides; without colours it stays as it is, W25-R55). */
const OWN_SCOPE = ':not([data-square-theme])[data-own-colours]'

/** What the owner chose on top of the theme; a missing part leaves the theme as designed. */
export interface ThemeOverrides { colors?: Seeds | null; colors_dark?: Seeds | null; fonts?: string | null; spinners?: string[] | null; shape?: ShapeChoice | null; feel?: FeelChoice | null; type?: TypeChoice | null }

/** Declarations for one mode: the --t-* colours, the Tailwind bridge and the panel colours, as the generator writes them for an engine theme. */
function declarations(p: Palette, mode: Mode): string {
  const tk: TokenMap = deriveColourTokens(p, mode)
  const dark = mode === 'dark'
  let sec = p.acc2 ?? p.g
  const lumLow = contrastRatio(sec, '#000000') < 7 // the generator's test lum(sec) < 0.3, written as a ratio against black
  if (dark || lumLow) sec = mix(sec, '#ffffff', 0.45)
  const onSec = contrastRatio('#111111', sec) >= contrastRatio('#ffffff', sec) ? '#111111' : '#ffffff'
  let ivm = p.ivm
  for (let t = 0; contrastRatio(ivm, p.inv) < 4.5 && t < 1; ) {
    t += 0.02
    ivm = mix(p.ivm, p.iv, t)
  }
  const all: TokenMap = {
    ...tk,
    '--color-bg': tk['--t-bg'], '--color-surface': tk['--t-surface'], '--color-border': tk['--t-border'],
    '--color-primary': tk['--t-accent'], '--color-secondary': sec, '--color-accent': sec, '--color-on-secondary': onSec,
    '--color-text': tk['--t-text-strong'], '--color-text-secondary': tk['--t-text-muted'],
    '--color-success': tk['--t-success'], '--color-success-bg': tk['--t-success-bg'], '--color-error': tk['--t-danger'], '--color-error-bg': tk['--t-danger-bg'],
    '--lt-panel': p.inv, '--lt-p': p.inv, '--lt-pi': p.iv, '--lt-pa': ivm, '--lt-ao': p.inv, '--lt-ivm': ivm,
  }
  return Object.entries(all).map(([k, v]) => `${k}:${v};`).join('')
}

const seedsOk = (s: Seeds | null | undefined): s is Seeds => !!s && isHex(s.bg) && isHex(s.ink) && isHex(s.acc)

/** The colour rules. `seeds` are the three colours of the look the theme opens in; `dark` (W18-R52) are the dark look's own three colours, else the dark look is made from `seeds`. */
function colourCss(seeds: Seeds | null | undefined, seedMode: Mode, dark?: Seeds | null): string {
  const lightOk = seedsOk(seeds)
  const darkOk = seedsOk(dark)
  if (!lightOk && !darkOk) return ''
  const A = '[data-square-theme]'
  const scopeOnly = (d: string) => d.split(';').filter((x) => !x.startsWith('--color-')).join(';')
  const bridgeOnly = (d: string) => d.split(';').filter((x) => x.startsWith('--color-')).join(';')
  const out: string[] = []
  if (lightOk) {
    const L = declarations(paletteFromSeeds(seeds, 'light', seedMode), 'light')
    out.push(`html${A} .ds-scope.ds-scope{${scopeOnly(L)}}`, `html${A}${A}{${bridgeOnly(L)}}`)
  }
  const D = declarations(darkOk ? paletteFromSeeds(dark, 'dark', 'dark') : paletteFromSeeds(seeds as Seeds, 'dark', seedMode), 'dark')
  out.push(
    `html.dark${A} .ds-scope.ds-scope{color-scheme:dark;${scopeOnly(D)}}`,
    `html${A} .ds-scope.ds-scope.ds-force-dark{color-scheme:dark;${scopeOnly(D)}}`,
    `html.dark${A}${A}{${bridgeOnly(D)}}`,
  )
  return out.join('\n')
}

/** The font tokens of a pair, the same in light and dark. The admin and member pages pin their own (src/styles/admin-type.css). */
function fontCss(pair: FontPair): string {
  const display = fontStack(pair.display, pair.serif)
  const body = fontStack(pair.body, false)
  const A = '[data-square-theme]'
  return [
    `html${A} .ds-scope.ds-scope{--t-font-display:${display};--t-font-body:${body};--t-font-display-weight:${pair.displayWeight};--t-tab-family:${body};}`,
    `html${A}${A}{--font-sans:${body};}`,
  ].join('\n')
}

/** paper-brick has no theme id and reads its type from --ds-font-*: with an own font pair the same pair goes there through the marker `data-own-fonts` (W25-R55). The console keeps its fixed type (admin-type.css). */
function ownFontCss(pair: FontPair | null, type: TypeChoice | null): string {
  const display = type?.display ? faceStack(type.display) : pair ? fontStack(pair.display, pair.serif) : ''
  const body = type?.body ? faceStack(type.body) : pair ? fontStack(pair.body, false) : ''
  if (!display && !body) return ''
  const A = ':not([data-square-theme])[data-own-fonts]'
  const scope = [display && `--ds-font-display:${display};--ds-font-editorial:${display};`, body && `--ds-font-body:${body};`].join('')
  return `html${A} .ds-scope.ds-scope{${scope}}` + (body ? `\nhtml${A}{--font-sans:${body};}` : '')
}

/** The owner's own heading, body and accent fonts (W25-R63) on a themed square; a single-weight heading font fixes the heading weight so the browser never fakes a bold. The accent lines
 *  (`--ds-font-script`) are set for every square, paper-brick too. */
function typeCss(t: TypeChoice | null): string {
  if (!t) return ''
  const A = '[data-square-theme]'
  const out: string[] = []
  if (t.display || t.body) {
    const scope = [
      t.display ? `--t-font-display:${faceStack(t.display)};` : '',
      t.display && t.display.w.length === 1 ? `--t-font-display-weight:${t.display.w[0]};` : '',
      t.body ? `--t-font-body:${faceStack(t.body)};` : '',
    ].join('')
    out.push(`html${A} .ds-scope.ds-scope{${scope}}`)
    if (t.body) out.push(`html${A}${A}{--font-sans:${faceStack(t.body)};}`)
  }
  const accent = accentStack(t)
  if (accent) out.push(`html:root .ds-scope.ds-scope{--ds-font-script:${accent};}`)
  return out.join('\n')
}

/** The CSS of the override, or '' when nothing valid was asked. Specificity is one class above the generated rules, so it always wins. */
export function themeOverrideCss(o: ThemeOverrides, seedMode: Mode = 'light'): string {
  const parts: string[] = []
  if (o.colors || o.colors_dark) parts.push(colourCss(o.colors, seedMode, o.colors_dark))
  const pair = fontPairById(o.fonts)
  if (pair) parts.push(fontCss(pair))
  parts.push(typeCss(cleanType(o.type)))
  parts.push(shapeCss(o.shape))
  parts.push(feelCss(o.feel))
  return parts.filter(Boolean).join('\n')
}

/** Writes the override (replacing an earlier one) and loads the font pair; null removes both. Returns false when nothing valid was asked.
 *  seedMode: 'dark' for a theme that opens dark (layout-themes `opensDark`): its three colours then describe the dark look (W18-R21). */
export function applyThemeOverrides(o: ThemeOverrides | null, doc: Document = document, seedMode: Mode = 'light'): boolean {
  doc.getElementById(STYLE_ID)?.remove()
  delete doc.documentElement.dataset.ownColours
  delete doc.documentElement.dataset.ownFonts
  doc.querySelector(`link[${LINK_ATTR}]`)?.remove()
  doc.querySelector(`link[${CUSTOM_LINK_ATTR}]`)?.remove()
  if (!o) return true
  const css = themeOverrideCss(o, seedMode)
  if (!css) return false
  const el = doc.createElement('style')
  el.id = STYLE_ID
  const colourOnly = seedsOk(o.colors) || seedsOk(o.colors_dark)
  const fontPair = fontPairById(o.fonts)
  const type = cleanType(o.type)
  const ownFonts = ownFontCss(fontPair, type)
  // the same colour and font rules once more, for paper-brick (no theme id)
  el.textContent = [css, colourOnly ? colourCss(o.colors, seedMode, o.colors_dark).split('[data-square-theme]').join(OWN_SCOPE) : '', ownFonts].filter(Boolean).join('\n')
  doc.head.appendChild(el)
  if (colourOnly) doc.documentElement.dataset.ownColours = ''
  if (ownFonts) doc.documentElement.dataset.ownFonts = ''
  const customUrl = typeUrl(type)
  if (customUrl) {
    const link = doc.createElement('link')
    link.rel = 'stylesheet'
    link.href = customUrl
    link.setAttribute(CUSTOM_LINK_ATTR, '1')
    doc.head.appendChild(link)
  }
  const pair = fontPairById(o.fonts)
  if (pair) {
    const link = doc.createElement('link')
    link.rel = 'stylesheet'
    link.href = pair.url
    link.setAttribute(LINK_ATTR, pair.id)
    doc.head.appendChild(link)
  }
  return true
}

/** The saved look with a preview on top: a part the preview sets replaces the saved part; a part it leaves out stays. Null when neither has anything. */
export function mergeOverrides(saved: ThemeOverrides | null | undefined, preview: ThemeOverrides | null | undefined): ThemeOverrides | null {
  const colors = preview?.colors ?? saved?.colors ?? null
  const colorsDark = preview?.colors_dark ?? saved?.colors_dark ?? null
  const fonts = preview?.fonts ?? saved?.fonts ?? null
  const shape = cleanShape(preview?.shape) ?? cleanShape(saved?.shape)
  const feel = cleanFeel(preview?.feel) ?? cleanFeel(saved?.feel)
  const type = cleanType(preview?.type) ?? cleanType(saved?.type)
  if (!(colors || colorsDark || fonts || shape || feel || type)) return null
  return { colors, fonts, ...(colorsDark ? { colors_dark: colorsDark } : {}), ...(shape ? { shape } : {}), ...(feel ? { feel } : {}), ...(type ? { type } : {}) }
}

/** `bg,ink,accent` as hex without # (or with), to seeds; null when it is not three colours. */
export function parseColors(v: string | null): Seeds | null {
  if (!v) return null
  const parts = v.split(',').map((x) => '#' + x.trim().replace(/^#/, ''))
  if (parts.length !== 3 || !parts.every(isHex)) return null
  return { bg: parts[0], ink: parts[1], acc: parts[2] }
}

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

/** Development and demo mode only: ?colors=bg,ink,acc and ?fonts=<pair id> preview own colours and fonts, `off` removes them; kept for the tab. Null when neither is set. */
export function previewOverrides(search: string, storage: Store): ThemeOverrides | null {
  const q = new URLSearchParams(search)
  const colors = q.get('colors')
  if (colors === 'off') storage.removeItem(KEY)
  else if (colors && parseColors(colors)) storage.setItem(KEY, colors)
  const dcolors = q.get('dcolors')
  if (dcolors === 'off') storage.removeItem(DARK_KEY)
  else if (dcolors && parseColors(dcolors)) storage.setItem(DARK_KEY, dcolors)
  const fonts = q.get('fonts')
  if (fonts === 'off') storage.removeItem(FONT_KEY)
  else if (fonts && fontPairById(fonts)) storage.setItem(FONT_KEY, fonts)
  const shape = q.get('shape')
  if (shape === 'off') storage.removeItem(SHAPE_KEY)
  else if (shape && parseShape(shape)) storage.setItem(SHAPE_KEY, shapeText(parseShape(shape)))
  const o: ThemeOverrides = { colors: parseColors(storage.getItem(KEY)), fonts: fontPairById(storage.getItem(FONT_KEY))?.id ?? null }
  const chosen = parseShape(storage.getItem(SHAPE_KEY))
  if (chosen) o.shape = chosen
  const darkColours = parseColors(storage.getItem(DARK_KEY))
  if (darkColours) o.colors_dark = darkColours
  const feel = q.get('feel')
  if (feel === 'off') storage.removeItem(FEEL_KEY)
  else if (feel && parseFeel(feel)) storage.setItem(FEEL_KEY, feelText(parseFeel(feel)))
  const felt = parseFeel(storage.getItem(FEEL_KEY))
  if (felt) o.feel = felt
  return o.colors || o.colors_dark || o.fonts || o.shape || o.feel ? o : null
}
