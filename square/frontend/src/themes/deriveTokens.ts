/**
 * What it is:   The colour part of a theme, in the browser (rootsquares W18, docs/plans/themes-dynamic-plan.md).
 * What it does: deriveColourTokens() turns a theme's 14 colours into the `--t-*` colour tokens, the same way tokens() in
 *               scripts/build_layout_themes.py does (a port; deriveTokens.spec.ts proves they agree for all 56 themes).
 *               paletteFromSeeds() builds the 14 colours (light and dark) from three colours an owner picks: background, text, accent
 *               (the seeds describe the light look, or the dark look for a theme that opens dark).
 * How to use:   import { paletteFromSeeds, deriveColourTokens } from './deriveTokens'. Nothing is applied to the page here.
 * Run:          from square/frontend: npx vitest run src/themes/deriveTokens.spec.ts
 * Read before:  docs/plans/themes-dynamic-plan.md; tokens() in scripts/build_layout_themes.py (the reference).
 * Read after:   the step that applies the tokens to <html> (not built yet).
 *
 * If the generator's colour rules change, change this file the same way; the parity test fails until both agree.
 */

export type Mode = 'light' | 'dark'

/** The 14 colours of a theme (design/tenant-themes-v7/themes.json, keys `l` and `d`). `acc2` exists on the reference themes only. */
export interface Palette {
  bg: string; card: string; sunk: string; ink: string; body: string; mute: string; line: string
  acc: string; on: string; g: string; hl: string; inv: string; iv: string; ivm: string
  acc2?: string
}

export type TokenMap = Record<string, string>

const STATUS: Record<Mode, Record<string, string>> = {
  light: { success: '#1F5233', 'success-bg': '#E1EFE6', warning: '#5C3A00', 'warning-bg': '#FBEBC8', danger: '#8A1F14', 'danger-bg': '#FBE3DF', info: '#1E4A7A', 'info-bg': '#E0ECF8' },
  dark: { success: '#A9DDB9', 'success-bg': '#17301F', warning: '#F2D08A', 'warning-bg': '#35290C', danger: '#F3B2A8', 'danger-bg': '#3B1A15', info: '#B5D3F0', 'info-bg': '#152B40' },
}

type Rgb = [number, number, number]

function rgb(h: string): Rgb {
  let s = h.replace(/^#/, '')
  if (s.length === 3) s = s.split('').map((c) => c + c).join('')
  return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)]
}

/** Python's round(): halves go to the even number (JavaScript's Math.round does not). */
function roundHalfEven(v: number): number {
  const f = Math.floor(v)
  const d = v - f
  if (d < 0.5) return f
  if (d > 0.5) return f + 1
  return f % 2 === 0 ? f : f + 1
}

function hexc(c: number[]): string {
  return '#' + c.map((v) => Math.max(0, Math.min(255, roundHalfEven(v))).toString(16).padStart(2, '0')).join('')
}

function lum(h: string): number {
  const ch = (v: number) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  const [r, g, b] = rgb(h).map(ch)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrastRatio(a: string, b: string): number {
  const x = lum(a)
  const y = lum(b)
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}

/** t = share of b. */
export function mix(a: string, b: string, t: number): string {
  const ra = rgb(a)
  const rb = rgb(b)
  return hexc([0, 1, 2].map((i) => ra[i] + (rb[i] - ra[i]) * t))
}

/** The nearest shade of c (moving toward `toward`) that reaches `need` on every ground. */
function fix(c: string, grounds: string[], need: number, toward: string): string {
  let x = c
  let t = 0
  while (!grounds.every((g) => contrastRatio(x, g) >= need) && t < 1) {
    t += 0.02
    x = mix(c, toward, t)
  }
  return x
}

/** The first of the options with the best ratio on `on` (ties keep the earlier option, like Python's max). */
function bestOn(options: string[], on: string): string {
  let best = options[0]
  for (const o of options) if (contrastRatio(o, on) > contrastRatio(best, on)) best = o
  return best
}

export function deriveColourTokens(c: Palette, mode: Mode): TokenMap {
  const dark = mode === 'dark'
  const { bg, card, sunk, ink, body, mute, line } = c
  const blackWhite = dark ? '#ffffff' : '#000000'
  const grounds = [bg, card, sunk, c.hl]
  const strong = fix(ink, grounds, 7, blackWhite)
  const text = fix(body, grounds, 4.5, ink)
  const muted = fix(mute, grounds, 4.5, ink)
  const link = fix(c.acc, grounds, 4.5, ink)
  const g = c.acc2 ?? c.g
  const accentText = fix(c.g, grounds, 4.5, ink)
  let accent = c.acc
  const onPrimary = bestOn([c.on, '#ffffff', '#111111'], accent)
  if (contrastRatio(onPrimary, accent) < 4.5) {
    const toward = lum(onPrimary) > 0.5 ? '#000000' : '#ffffff'
    let x = accent
    let tt = 0
    while (contrastRatio(onPrimary, x) < 4.5 && tt < 1) {
      tt += 0.02
      x = mix(c.acc, toward, tt)
    }
    accent = x
  }
  const onAccent = bestOn(['#ffffff', '#111111'], g)
  const hover = mix(accent, dark ? '#ffffff' : '#000000', dark ? 0.1 : 0.12)
  const press = mix(accent, dark ? '#ffffff' : '#000000', dark ? 0.2 : 0.24)
  const borderDefault = mix(line, mute, 0.4)
  const borderStrong = fix(mix(line, mute, 0.8), [bg, card], 3, strong)
  const out: TokenMap = {
    '--t-bg': bg, '--t-surface': card, '--t-surface-sunken': sunk, '--t-inverse': c.inv,
    '--t-accent-soft': mix(card, g, 0.28), '--t-primary-soft': c.hl,
    '--t-text-strong': strong, '--t-text': text, '--t-text-muted': muted, '--t-on-inverse': c.iv,
    '--t-on-primary': onPrimary, '--t-link': link, '--t-accent-text': accentText, '--t-on-accent': onAccent,
    '--t-border': line, '--t-border-default': borderDefault, '--t-border-strong': borderStrong,
    '--t-accent': accent, '--t-accent-hover': hover, '--t-accent-press': press, '--t-accent-2': g,
    '--t-focus': link, '--t-btn-border': accent,
  }
  for (const [k, v] of Object.entries(STATUS[mode])) out[`--t-${k}`] = v
  return out
}

/** The three colours an owner picks. All must be #rrggbb or #rgb. */
export interface Seeds { bg: string; ink: string; acc: string }

export function isHex(v: string): boolean {
  return /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(v)
}

/**
 * The 14 colours from three seeds, for one mode. `seedMode` says which look the seeds describe: the LIGHT look for a theme that opens light (all but four),
 * the DARK look for a theme that opens dark (mela-noir, neon-cyan, citrus-night, mint-night; W18-R21). The other look is derived from the same three
 * (the owner's decision, W18-R14): from light seeds a dark ground tinted by the text colour, text from the light ground and a lifted accent; from dark seeds
 * the mirror, a pale ground tinted by the text colour, text from the dark ground and a deepened accent.
 * A ground or text colour that cannot be read (for example text as light as its ground) is moved toward black or white first,
 * so the contrast corrections of deriveColourTokens() can always succeed.
 */
export function paletteFromSeeds(s: Seeds, mode: Mode, seedMode: Mode = 'light'): Palette {
  const full = (v: string) => (v.length === 4 ? '#' + v.slice(1).split('').map((x) => x + x).join('') : v)
  const bg0 = full(s.bg)
  const ink0 = full(s.ink)
  const acc0 = full(s.acc)
  const dark = mode === 'dark'
  // the starting colours of this mode: the seeds themselves when they describe this mode, otherwise derived from them
  const same = mode === seedMode
  const baseBg = same ? bg0 : dark ? mix(ink0, '#000000', 0.55) : mix(ink0, '#ffffff', 0.9)
  const baseInk = same ? ink0 : dark ? mix(bg0, '#ffffff', 0.3) : mix(bg0, '#000000', 0.4)
  const baseAcc = same ? acc0 : dark ? mix(acc0, '#ffffff', 0.25) : mix(acc0, '#000000', 0.25)
  const extreme = dark ? '#ffffff' : '#000000'
  const far = dark ? '#000000' : '#ffffff'
  const grounds = (bg: string, acc: string) => {
    const card = dark ? mix(bg, '#ffffff', 0.06) : mix(bg, '#ffffff', 0.5)
    const sunk = dark ? mix(bg, '#000000', 0.3) : mix(bg, baseInk, 0.05)
    const hl = mix(bg, acc, dark ? 0.2 : 0.12)
    return { card, sunk, hl }
  }
  // 1. the ground: dark enough (dark mode) or light enough (light mode) that the strongest text can reach 7:1 on every surface
  let bg = baseBg
  const acc = baseAcc
  for (let t = 0; t < 1; t += 0.02) {
    const g = grounds(bg, acc)
    if ([bg, g.card, g.sunk, g.hl].every((x) => contrastRatio(extreme, x) >= 7)) break
    bg = mix(baseBg, far, t + 0.02)
  }
  const g = grounds(bg, acc)
  // 2. the text: the starting colour, or the nearest shade of it that reaches 7:1 on every surface
  const ink = fix(baseInk, [bg, g.card, g.sunk, g.hl], 7, extreme)
  const inv = dark ? mix(bg, '#000000', 0.35) : mix(baseInk, '#000000', 0.25)
  const iv = dark ? ink : baseBg
  return {
    bg, card: g.card, sunk: g.sunk, ink,
    body: mix(ink, bg, 0.25), mute: mix(ink, bg, 0.45), line: mix(bg, ink, dark ? 0.2 : 0.15),
    acc, on: bestOn(['#ffffff', '#111111'], acc), g: acc,
    hl: g.hl,
    inv, iv, ivm: mix(iv, inv, 0.4),
  }
}
