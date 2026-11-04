// Tests for shapes.ts (button, card, photo frame and edge shapes, W18 shapes steps 2 to 4) and its wiring in applyThemeOverrides.ts: the options, the CSS of a choice, the ?shape= preview, the merge with a saved look.
// Run from square/frontend: npx vitest run src/themes/shapes.spec.ts
import { describe, expect, it } from 'vitest'
import { mergeOverrides, previewOverrides, themeOverrideCss } from './applyThemeOverrides'
import { BUTTON_SHAPE_IDS, CARD_SHAPE_IDS, EDGE_SHAPE_IDS, PHOTO_SHAPE_IDS, cleanShape, parseShape, shapeCss, shapeText } from './shapes'

function store(init: Record<string, string> = {}) {
  const m = new Map(Object.entries(init))
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), removeItem: (k: string) => void m.delete(k) }
}

describe('the options', () => {
  it('has four button shapes, three card shapes, five photo frames and four edges', () => {
    expect(BUTTON_SHAPE_IDS).toEqual(['square', 'soft', 'rounded', 'pill'])
    expect(CARD_SHAPE_IDS).toEqual(['square', 'soft', 'rounded'])
    expect(PHOTO_SHAPE_IDS).toEqual(['square', 'soft', 'rounded', 'arch', 'circle'])
    expect(EDGE_SHAPE_IDS).toEqual(['flat', 'line', 'strong', 'shadow'])
  })
  it('keeps only options that exist and leaves out parts that are not chosen', () => {
    expect(cleanShape({ buttons: 'pill', cards: 'nope' })).toEqual({ buttons: 'pill' })
    expect(cleanShape({ buttons: 'blob', cards: 'blob', photos: 'toString' })).toBeNull()
    expect(cleanShape(null)).toBeNull()
  })
})

describe('shapeCss: buttons and cards', () => {
  it('sets every button knob (themes and paper-brick) for a button choice, above the generated rules', () => {
    const css = shapeCss({ buttons: 'pill' })
    expect(css).toContain('html:root .ds-scope.ds-scope{')
    expect(css).toContain('--t-radius-btn:999px;')
    expect(css).toContain('--ds-radius-pill:999px;')
    expect(css).not.toContain('--lt-r:')
  })
  it('sets every card knob, including the layout-theme card radius', () => {
    const css = shapeCss({ cards: 'rounded' })
    for (const k of ['--t-radius-sm:8px;', '--t-radius:14px;', '--t-radius-lg:22px;', '--ds-radius-sm:8px;', '--ds-radius-md:14px;', '--ds-radius-lg:22px;', '--lt-r:22px;']) expect(css).toContain(k)
    expect(css).not.toContain('--t-radius-btn')
  })
  it('pins the console to the design system corners, after the public rule', () => {
    const lines = shapeCss({ buttons: 'square', cards: 'square' }).split('\n')
    expect(lines[1]).toBe('html:root .ds-appshell.ds-appshell{--ds-radius-sm:6px;--ds-radius-md:10px;--ds-radius-lg:18px;--ds-radius-pill:999px;}')
  })
})

describe('shapeCss: photo frames and edges', () => {
  it('puts the frame on the public frame classes, never inside the console, and wins over inline corners', () => {
    const css = shapeCss({ photos: 'arch' })
    expect(css).toContain('html:root .ds-scope.ds-scope .lt-photo:not(.ds-appshell .lt-photo)')
    expect(css).toContain('border-radius:999px 999px 0 0 !important;')
    expect(css).not.toContain('--t-radius')
  })
  it('circle rounds people and rounds the other photos', () => {
    const lines = shapeCss({ photos: 'circle' }).split('\n')
    expect(lines[0]).toContain('border-radius:22px !important;')
    expect(lines[1]).toContain('.ds-founder-portrait .ds-arch-inner')
    expect(lines[1]).toContain('border-radius:50% !important;')
  })
  it('edges set border and shadow on cards and frames', () => {
    expect(shapeCss({ edges: 'line' })).toMatch(/\.ds-card:not\(\.ds-appshell \.ds-card\).*\.lt-photo.*\{border:1px solid var\(--t-border, #d8d2c8\) !important;box-shadow:none !important;\}/)
    expect(shapeCss({ edges: 'shadow' })).toContain('box-shadow:0 10px 28px -10px')
    expect(shapeCss({ edges: 'flat' })).toContain('border:0 solid transparent !important;')
  })
})

describe('shapeCss: safety', () => {
  it('never touches colour or text size', () => {
    expect(shapeCss({ buttons: 'pill', cards: 'soft', photos: 'arch', edges: 'strong' })).not.toMatch(/--t-(bg|text-muted|accent|font)|--color-|font-size/)
  })
  it('gives nothing for nothing or for unknown ids', () => {
    expect(shapeCss(null)).toBe('')
    expect(shapeCss({ buttons: 'blob', photos: 'hexagon' })).toBe('')
  })
})

describe('the preview and the merge', () => {
  it('parses the preview text, drops bad parts and round-trips', () => {
    expect(parseShape('buttons:pill,cards:soft')).toEqual({ buttons: 'pill', cards: 'soft' })
    expect(parseShape('buttons:pill,cards:blob,edges:line,photos:arch')).toEqual({ buttons: 'pill', edges: 'line', photos: 'arch' })
    expect(parseShape('junk')).toBeNull()
    expect(shapeText({ buttons: 'pill', cards: 'soft', photos: 'arch', edges: 'line' })).toBe('buttons:pill,cards:soft,photos:arch,edges:line')
  })
  it('?shape= is kept for the tab and ?shape=off removes it', () => {
    const s = store()
    expect(previewOverrides('?shape=buttons:rounded', s)?.shape).toEqual({ buttons: 'rounded' })
    expect(previewOverrides('', s)?.shape).toEqual({ buttons: 'rounded' })
    expect(previewOverrides('?shape=off', s)).toBeNull()
  })
  it('a previewed part replaces the saved part and a part it leaves out stays', () => {
    const merged = mergeOverrides({ shape: { buttons: 'square', cards: 'soft' } }, { shape: { buttons: 'pill' } })
    expect(merged?.shape).toEqual({ buttons: 'pill' })
    expect(mergeOverrides({ shape: { buttons: 'square' } }, null)?.shape).toEqual({ buttons: 'square' })
    expect(mergeOverrides(null, null)).toBeNull()
  })
  it('themeOverrideCss carries the shape beside colours and fonts', () => {
    expect(themeOverrideCss({ shape: { cards: 'soft' } })).toContain('--lt-r:12px;')
    expect(themeOverrideCss({ shape: { buttons: 'blob' } })).toBe('')
  })
})
