// Tests for feel.ts (the Feel tab: default mode, switch, density, motion, W18-R44) and its wiring in applyThemeOverrides.ts: the options, the CSS, the mode rule, the ?feel= preview, the merge.
// Run from square/frontend: npx vitest run src/themes/feel.spec.ts
import { describe, expect, it } from 'vitest'
import { mergeOverrides, previewOverrides, themeOverrideCss } from './applyThemeOverrides'
import { FEEL_OPTIONS, cleanFeel, feelCss, feelMode, feelText, parseFeel } from './feel'

function store(init: Record<string, string> = {}) {
  const m = new Map(Object.entries(init))
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), removeItem: (k: string) => void m.delete(k) }
}

describe('the options', () => {
  it('has the six parts with their options', () => {
    expect(FEEL_OPTIONS).toEqual({ mode: ['light', 'dark', 'system'], switch: ['show', 'hide'], density: ['compact', 'comfortable', 'airy'], text: ['normal', 'large', 'xlarge'], motion: ['lively', 'nolift', 'nostrip', 'calm'], divider: ['glyph', 'line', 'none'] })
  })
  it('keeps only options that exist and leaves out parts that are not chosen', () => {
    expect(cleanFeel({ mode: 'dark', density: 'huge' })).toEqual({ mode: 'dark' })
    expect(cleanFeel({ mode: 'purple', motion: 'toString' })).toBeNull()
    expect(cleanFeel(null)).toBeNull()
  })
})

describe('feelCss', () => {
  it('density sets the section tokens and the layout-theme section padding, with a phone rule, and keeps the console spacing', () => {
    const css = feelCss({ density: 'airy' })
    expect(css).toContain('--ds-section-y:132px;')
    expect(css).toContain('.lt-sec:not(:first-child){padding-top:120px !important;}')
    expect(css).toContain('@media (max-width:720px)')
    expect(css).toContain('html:root .ds-appshell.ds-appshell{--ds-space-5:24px;')
    expect(feelCss({ density: 'compact' })).toContain('--ds-section-y:56px;')
  })
  it('motion calm pauses the tickers and the hover lift; nolift only the lift, nostrip only the strips; the old none is calm (W25-R57)', () => {
    const calm = feelCss({ motion: 'calm' })
    expect(calm).toContain('animation-play-state:paused !important;')
    expect(calm).toContain('.ds-card:hover')
    expect(calm).not.toContain('animation:none')
    const lift = feelCss({ motion: 'nolift' })
    expect(lift).toContain('.ds-card:hover')
    expect(lift).not.toContain('animation-play-state')
    const strip = feelCss({ motion: 'nostrip' })
    expect(strip).toContain('animation-play-state:paused !important;')
    expect(strip).not.toContain('.ds-card:hover')
    expect(feelCss({ motion: 'none' })).toBe(calm)
    expect(cleanFeel({ motion: 'none' })).toEqual({ motion: 'calm' })
  })
  it('lively and show leave the page as designed', () => {
    expect(feelCss({ motion: 'lively', switch: 'show' })).toBe('')
    expect(feelCss({ mode: 'dark' })).toBe('')
  })
  it('hiding the switch hides both toggles on the public pages, not in the console', () => {
    const css = feelCss({ switch: 'hide' })
    expect(css).toContain('.ds-theme-toggle:not(.ds-appshell .ds-theme-toggle)')
    expect(css).toContain('.lt-mode:not(.ds-appshell .lt-mode)')
    expect(css).toContain('display:none !important;')
  })
  it('never touches colour, fonts or corners', () => {
    expect(feelCss({ density: 'airy', motion: 'calm', switch: 'hide', text: 'large', divider: 'none' })).not.toMatch(/--t-|--color-|font-|radius/)
  })
})

describe('text size and divider', () => {
  it('large and extra large zoom the outermost public scope only, never the console', () => {
    expect(feelCss({ text: 'large' })).toContain(':not(.ds-scope .ds-scope):not(:has(.ds-appshell)){zoom:1.12;}')
    expect(feelCss({ text: 'xlarge' })).toContain('zoom:1.25;')
    expect(feelCss({ text: 'normal' })).toContain('zoom:1;')
  })
  it('the divider line hides the glyph, none hides the whole motif, glyph leaves it as designed; never in the console', () => {
    expect(feelCss({ divider: 'line' })).toContain('.ds-motif-glyph:not(.ds-appshell .ds-motif-glyph){display:none !important;}')
    expect(feelCss({ divider: 'none' })).toContain('.ds-motif:not(.ds-appshell .ds-motif){display:none !important;}')
    expect(feelCss({ divider: 'glyph' })).toBe('')
  })
  it('the preview text carries all six parts', () => {
    expect(parseFeel('text:large,divider:line')).toEqual({ text: 'large', divider: 'line' })
    expect(feelText({ mode: 'dark', switch: 'hide', density: 'airy', text: 'large', motion: 'calm', divider: 'none' })).toBe('mode:dark,switch:hide,density:airy,text:large,motion:calm,divider:none')
  })
})

describe('feelMode', () => {
  it('is null when the owner chose no mode (the usual rule applies)', () => {
    expect(feelMode(null, 'dark', true)).toBeNull()
    expect(feelMode({ density: 'airy' }, null, false)).toBeNull()
  })
  it('gives the owner default when the visitor has not chosen, and `system` follows the device', () => {
    expect(feelMode({ mode: 'dark' }, null, false)).toBe('dark')
    expect(feelMode({ mode: 'light' }, null, true)).toBe('light')
    expect(feelMode({ mode: 'system' }, null, true)).toBe('dark')
    expect(feelMode({ mode: 'system' }, null, false)).toBe('light')
  })
  it('the visitor\'s own choice wins while the switch is shown, and loses when it is hidden', () => {
    expect(feelMode({ mode: 'dark' }, 'light', false)).toBe('light')
    expect(feelMode({ mode: 'dark', switch: 'show' }, 'light', false)).toBe('light')
    expect(feelMode({ mode: 'dark', switch: 'hide' }, 'light', false)).toBe('dark')
  })
})

describe('the preview and the merge', () => {
  it('parses the preview text, drops bad parts and round-trips', () => {
    expect(parseFeel('mode:dark,density:airy')).toEqual({ mode: 'dark', density: 'airy' })
    expect(parseFeel('mode:blue,motion:calm,x:y')).toEqual({ motion: 'calm' })
    expect(parseFeel('junk')).toBeNull()
    expect(feelText({ mode: 'dark', switch: 'hide', density: 'airy', motion: 'calm' })).toBe('mode:dark,switch:hide,density:airy,motion:calm')
  })
  it('?feel= is kept for the tab and ?feel=off removes it', () => {
    const s = store()
    expect(previewOverrides('?feel=density:compact', s)?.feel).toEqual({ density: 'compact' })
    expect(previewOverrides('', s)?.feel).toEqual({ density: 'compact' })
    expect(previewOverrides('?feel=off', s)).toBeNull()
  })
  it('a previewed feel replaces the saved one; shapes and feel travel together', () => {
    expect(mergeOverrides({ feel: { mode: 'dark' } }, { feel: { mode: 'light' } })?.feel).toEqual({ mode: 'light' })
    expect(mergeOverrides({ feel: { mode: 'dark' } }, null)?.feel).toEqual({ mode: 'dark' })
    const both = mergeOverrides({ shape: { buttons: 'pill' } }, { feel: { motion: 'calm' } })
    expect(both?.shape).toEqual({ buttons: 'pill' })
    expect(both?.feel).toEqual({ motion: 'calm' })
  })
  it('themeOverrideCss carries the feel beside the rest', () => {
    expect(themeOverrideCss({ feel: { density: 'airy' } })).toContain('--ds-section-y:132px;')
    expect(themeOverrideCss({ feel: { mode: 'dark' } })).toBe('')
  })
})
