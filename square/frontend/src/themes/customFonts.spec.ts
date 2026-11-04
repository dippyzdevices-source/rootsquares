// Tests for customFonts.ts (the owner's own heading, body and accent fonts, W25-R63): what is accepted, the Google Fonts address, the CSS on a themed square and on paper-brick.
// Run from square/frontend: npx vitest run src/themes/customFonts.spec.ts
import { describe, expect, it } from 'vitest'
import { ACCENTS, accentStack, cleanType, faceStack, typeUrl } from './customFonts'
import { applyThemeOverrides, mergeOverrides, themeOverrideCss } from './applyThemeOverrides'
import { lookOf } from '../dev/previewBridge'

const lora = { f: 'Lora', c: 'serif', w: [400, 700] }
const karla = { f: 'Karla', c: 'sans-serif', w: [400, 700] }

describe('cleanType', () => {
  it('keeps a valid heading, body and accent', () => {
    expect(cleanType({ display: lora, body: karla, accent: 'dancing' })).toEqual({ display: lora, body: karla, accent: 'dancing' })
  })
  it('drops everything that could end up in CSS or an address', () => {
    expect(cleanType({ display: { f: 'Lora; } body { display:none', c: 'serif', w: [400] } })).toBeNull()
    expect(cleanType({ display: { f: 'Lora', c: 'comic', w: [400] } })).toBeNull()
    expect(cleanType({ body: { f: '../x', c: 'serif', w: [400] } })).toBeNull()
    expect(cleanType({ accent: 'comic-sans' })).toBeNull()
    expect(cleanType('Lora')).toBeNull()
    expect(cleanType(null)).toBeNull()
  })
  it('keeps weights to whole hundreds and at most four, and falls back to 400', () => {
    expect(cleanType({ body: { f: 'Karla', c: 'sans-serif', w: [700, 400, 450, 1000, 'x', 400, 500, 600, 800] } })?.body?.w).toEqual([400, 500, 600, 700])
    expect(cleanType({ body: { f: 'Karla', c: 'sans-serif', w: [] } })?.body?.w).toEqual([400])
  })
  it('has the accent ids the server offers', () => {
    expect(Object.keys(ACCENTS)).toEqual(['sacramento', 'dancing', 'caveat', 'great-vibes'])
    expect(cleanType({ accent: 'headings' })).toEqual({ accent: 'headings' })
  })
})

describe('typeUrl, faceStack, accentStack', () => {
  it('builds one Google Fonts address for the chosen families', () => {
    expect(typeUrl({ display: lora, body: { f: 'DM Sans', c: 'sans-serif', w: [400, 700] }, accent: 'caveat' })).toBe(
      'https://fonts.googleapis.com/css2?family=Lora:wght@400;700&family=DM+Sans:wght@400;700&family=Caveat:wght@400;700&display=swap')
    expect(typeUrl({ body: karla, display: karla })).toBe('https://fonts.googleapis.com/css2?family=Karla:wght@400;700&display=swap') // the same family once
    expect(typeUrl({ accent: 'headings' })).toBeNull()
    expect(typeUrl(null)).toBeNull()
  })
  it('gives a fallback by category', () => {
    expect(faceStack(lora)).toBe('"Lora",Georgia,serif')
    expect(faceStack({ f: 'Caveat', c: 'handwriting', w: [400] })).toBe('"Caveat",cursive')
    expect(accentStack({ accent: 'headings' })).toBe('var(--ds-font-display)')
    expect(accentStack({ accent: 'great-vibes' })).toBe('"Great Vibes",cursive')
    expect(accentStack({ display: lora })).toBeNull()
  })
})

describe('the CSS and the page', () => {
  it('a themed square gets the faces on its --t-font tokens, a single weight fixes the heading weight, the accent is set for every square', () => {
    const css = themeOverrideCss({ type: { display: { f: 'Gloock', c: 'serif', w: [400] }, body: karla, accent: 'dancing' } })
    expect(css).toContain('html[data-square-theme] .ds-scope.ds-scope{--t-font-display:"Gloock",Georgia,serif;--t-font-display-weight:400;--t-font-body:"Karla"')
    expect(css).toContain('html[data-square-theme][data-square-theme]{--font-sans:"Karla"')
    expect(css).toContain('html:root .ds-scope.ds-scope{--ds-font-script:"Dancing Script",cursive;}')
  })
  it('paper-brick gets them on --ds-font-* through the marker, the pair fills the role that is not chosen, a link loads the families', () => {
    applyThemeOverrides({ fonts: 'classic', type: { display: lora, accent: 'headings' } })
    const css = document.getElementById('rs-theme-overrides')!.textContent!
    expect(document.documentElement.dataset.ownFonts).toBe('')
    expect(css).toContain('html:not([data-square-theme])[data-own-fonts] .ds-scope.ds-scope{--ds-font-display:"Lora",Georgia,serif;--ds-font-editorial:"Lora",Georgia,serif;--ds-font-body:"Karla"')
    expect(css).toContain('--ds-font-script:var(--ds-font-display)')
    expect(document.querySelector('link[data-rs-font-custom]')?.getAttribute('href')).toBe('https://fonts.googleapis.com/css2?family=Lora:wght@400;700&display=swap')
    applyThemeOverrides(null)
    expect(document.querySelector('link[data-rs-font-custom]')).toBeNull()
    expect(document.documentElement.dataset.ownFonts).toBeUndefined()
  })
  it('only an accent is no font change of the page, but the accent line is set', () => {
    applyThemeOverrides({ type: { accent: 'caveat' } })
    expect(document.documentElement.dataset.ownFonts).toBeUndefined()
    expect(document.getElementById('rs-theme-overrides')!.textContent).toContain('--ds-font-script:"Caveat",cursive')
    applyThemeOverrides(null)
  })
  it('merge and the preview message carry the type', () => {
    expect(mergeOverrides({ type: { accent: 'caveat' } }, { type: { display: lora } })?.type).toEqual({ display: lora })
    expect(mergeOverrides({ type: { accent: 'caveat' } }, null)?.type).toEqual({ accent: 'caveat' })
    expect(lookOf({ type: { display: lora, accent: 'x' } })?.type).toEqual({ display: lora })
    expect(lookOf({ type: { display: { f: '<b>', c: 'serif', w: [400] } } })).toBeNull()
  })
})
