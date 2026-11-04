// Tests for applyThemeOverrides.ts and styles/admin-type.css (6 groups): the CSS built from colours and fonts, writing and removing the style and font link, the ?colors= and ?fonts= preview, the fixed admin type.
// Run from square/frontend: npx vitest run src/themes/applyThemeOverrides.spec.ts
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { applyThemeOverrides, mergeOverrides, parseColors, previewOverrides, themeOverrideCss } from './applyThemeOverrides'

const seeds = { bg: '#f6f1e7', ink: '#2b2a28', acc: '#c2410c' }

describe('themeOverrideCss (colours)', () => {
  it('covers light, dark, forced dark and the Tailwind bridge, each one class above the generated rules', () => {
    const css = themeOverrideCss({ colors: seeds })
    expect(css).toContain('html[data-square-theme] .ds-scope.ds-scope{')
    expect(css).toContain('html.dark[data-square-theme] .ds-scope.ds-scope{color-scheme:dark;')
    expect(css).toContain('.ds-scope.ds-scope.ds-force-dark{')
    expect(css).toContain('html[data-square-theme][data-square-theme]{--color-bg:')
    expect(css).toContain('--t-accent:#c2410c;')
    expect(css).toContain('--lt-p:')
  })
  it('keeps --color-* out of the .ds-scope rules and --t-* out of the html rules', () => {
    for (const line of themeOverrideCss({ colors: seeds }).split('\n')) {
      if (line.includes('.ds-scope')) expect(line).not.toContain('--color-')
      else expect(line).not.toContain('--t-')
    }
  })
  it('gives nothing for a bad colour, an unknown font pair, or nothing asked', () => {
    expect(themeOverrideCss({ colors: { ...seeds, acc: 'orange' } })).toBe('')
    expect(themeOverrideCss({ fonts: 'nope' })).toBe('')
    expect(themeOverrideCss({})).toBe('')
  })
})

describe('themeOverrideCss for a theme that opens dark', () => {
  const dark = { bg: '#101014', ink: '#ece8e1', acc: '#ff5a36' }
  it('puts the seed ground in the dark rule and a different, pale ground in the light rule', () => {
    const lines = themeOverrideCss({ colors: dark }, 'dark').split('\n')
    const light = lines.find((l) => l.startsWith('html[data-square-theme] .ds-scope.ds-scope{'))!
    const darkRule = lines.find((l) => l.startsWith('html.dark[data-square-theme] .ds-scope.ds-scope{'))!
    expect(darkRule).toContain('--t-bg:#101014;')
    expect(light).not.toContain('--t-bg:#101014;')
  })
  it('keeps the old result when no seed mode is given', () => {
    expect(themeOverrideCss({ colors: seeds })).toBe(themeOverrideCss({ colors: seeds }, 'light'))
  })
})

describe('themeOverrideCss (fonts)', () => {
  it('sets the font tokens and the Tailwind font for a pair, and no colour', () => {
    const css = themeOverrideCss({ fonts: 'soft' })
    expect(css).toContain('--t-font-display:"Quicksand","Helvetica Neue",Arial,sans-serif;')
    expect(css).toContain('--t-font-body:"Nunito","Helvetica Neue",Arial,sans-serif;')
    expect(css).toContain('--t-font-display-weight:700;')
    expect(css).toContain('html[data-square-theme][data-square-theme]{--font-sans:"Nunito"')
    expect(css).not.toContain('--t-bg')
  })
  it('uses the pair\'s own heaviest weight so no bold is faked', () => {
    expect(themeOverrideCss({ fonts: 'contemporary' })).toContain('--t-font-display-weight:400;')
    expect(themeOverrideCss({ fonts: 'editorial' })).toContain('"DM Serif Display",Georgia,serif')
  })
  it('puts colours and fonts together', () => {
    const css = themeOverrideCss({ colors: seeds, fonts: 'classic' })
    expect(css).toContain('--t-accent:#c2410c;')
    expect(css).toContain('"Marcellus"')
  })
})

describe('applyThemeOverrides', () => {
  it('writes one style element, replaces it, and removes it', () => {
    applyThemeOverrides({ colors: seeds })
    applyThemeOverrides({ colors: { ...seeds, acc: '#2563eb' } })
    expect(document.querySelectorAll('#rs-theme-overrides')).toHaveLength(1)
    expect(document.getElementById('rs-theme-overrides')!.textContent).toContain('#2563eb')
    applyThemeOverrides(null)
    expect(document.getElementById('rs-theme-overrides')).toBeNull()
  })
  it('loads the stylesheet of the font pair once, swaps it for another pair, and removes it', () => {
    applyThemeOverrides({ fonts: 'soft' })
    applyThemeOverrides({ fonts: 'soft' })
    const links = document.querySelectorAll('link[data-rs-font-pair]')
    expect(links).toHaveLength(1)
    expect((links[0] as HTMLLinkElement).href).toContain('family=Quicksand')
    applyThemeOverrides({ fonts: 'bold' })
    expect((document.querySelector('link[data-rs-font-pair]') as HTMLLinkElement).href).toContain('family=Space+Grotesk')
    applyThemeOverrides(null)
    expect(document.querySelector('link[data-rs-font-pair]')).toBeNull()
  })
  it('refuses bad input and leaves nothing behind', () => {
    expect(applyThemeOverrides({ colors: { ...seeds, bg: 'x' } })).toBe(false)
    expect(applyThemeOverrides({ fonts: 'nope' })).toBe(false)
    expect(document.getElementById('rs-theme-overrides')).toBeNull()
    expect(document.querySelector('link[data-rs-font-pair]')).toBeNull()
  })
})

describe('?colors= and ?fonts= preview', () => {
  const store = () => {
    const m = new Map<string, string>()
    return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), removeItem: (k: string) => void m.delete(k) }
  }
  it('parses three hex colours with or without #', () => {
    expect(parseColors('f6f1e7,2b2a28,#c2410c')).toEqual(seeds)
    expect(parseColors('f6f1e7,2b2a28')).toBeNull()
    expect(parseColors('zz,2b2a28,c2410c')).toBeNull()
  })
  it('remembers colours and fonts for the tab, ignores bad ones, and off removes each', () => {
    const s = store()
    expect(previewOverrides('', s)).toBeNull()
    expect(previewOverrides('?colors=f6f1e7,2b2a28,c2410c&fonts=soft', s)).toEqual({ colors: seeds, fonts: 'soft' })
    expect(previewOverrides('', s)).toEqual({ colors: seeds, fonts: 'soft' })
    expect(previewOverrides('?colors=nonsense&fonts=nope', s)).toEqual({ colors: seeds, fonts: 'soft' })
    expect(previewOverrides('?fonts=off', s)).toEqual({ colors: seeds, fonts: null })
    expect(previewOverrides('?colors=off', s)).toBeNull()
  })
})

describe('mergeOverrides', () => {
  it('lets a preview part replace the saved part and keeps the parts it leaves out', () => {
    expect(mergeOverrides(null, null)).toBeNull()
    expect(mergeOverrides({ colors: seeds, fonts: 'soft' }, null)).toEqual({ colors: seeds, fonts: 'soft' })
    expect(mergeOverrides({ colors: seeds, fonts: 'soft' }, { fonts: 'bold' })).toEqual({ colors: seeds, fonts: 'bold' })
    expect(mergeOverrides(undefined, { colors: seeds })).toEqual({ colors: seeds, fonts: null })
  })
})

describe('admin-type.css (the fixed type of the console and the portal)', () => {
  const read = (p: string) => readFileSync(resolve(process.cwd(), p), 'utf-8')
  const pin = read('src/styles/admin-type.css')
  const ds = read('src/styles/design-system.css')
  it('applies inside .ds-appshell, which both AdminLayout and MemberLayout use', () => {
    expect(pin).toContain('html[data-square-theme] .ds-appshell {')
    expect(read('src/layouts/AdminLayout.vue')).toContain('class="ds-appshell"')
    expect(read('src/layouts/MemberLayout.vue')).toContain('class="ds-appshell"')
  })
  it('pins the same fonts and tracking as the original design system', () => {
    for (const name of ['--ds-font-display', '--ds-font-editorial', '--ds-font-body']) {
      const want = ds.match(new RegExp(name + ':\\s*([^;]+);'))![1].trim()
      expect(pin).toContain(`${name}: ${want};`)
    }
    expect(pin).toContain('--ds-tracking-button: ' + ds.match(/--ds-tracking-button:\s*([^;]+);/)![1].trim() + ';')
  })
  it('pins every font knob the generated themes set', () => {
    for (const knob of ['--t-font-display', '--t-font-body', '--t-font-display-weight', '--t-btn-case', '--t-badge-case', '--t-tab-family', '--t-tab-case', '--t-eyebrow-case']) {
      expect(pin).toContain(knob + ':')
    }
  })
})

describe('dark colours of their own (W18-R52)', () => {
  const dark = { bg: '#101820', ink: '#e8efe9', acc: '#3ddc97' }
  const darkRule = (css: string) => css.split('\n').find((l) => l.startsWith('html.dark[data-square-theme] .ds-scope.ds-scope{')) ?? ''
  it('the dark look uses the dark colours, the light look still the light ones', () => {
    const css = themeOverrideCss({ colors: seeds, colors_dark: dark })
    expect(css).toContain('--t-accent:#c2410c;') // light
    expect(darkRule(css)).toContain('--t-bg:#101820;')
    expect(darkRule(css)).not.toEqual(darkRule(themeOverrideCss({ colors: seeds })))
    expect(css).toContain('.ds-scope.ds-scope.ds-force-dark{') // forced dark follows too
  })
  it('without them the dark look is made from the light colours, as before', () => {
    expect(themeOverrideCss({ colors: seeds, colors_dark: null })).toBe(themeOverrideCss({ colors: seeds }))
  })
  it('dark colours alone change only the dark look', () => {
    const css = themeOverrideCss({ colors_dark: dark })
    expect(css).toContain('html.dark[data-square-theme] .ds-scope.ds-scope{')
    expect(css).not.toContain('--color-bg:#f') // no light rule
    expect(css.split('\n').some((l) => l.startsWith('html[data-square-theme] .ds-scope.ds-scope{'))).toBe(false)
  })
  it('a bad dark colour changes nothing', () => {
    expect(themeOverrideCss({ colors: seeds, colors_dark: { bg: 'red', ink: '#000', acc: '#fff' } })).toBe(themeOverrideCss({ colors: seeds }))
  })
  it('merge and the ?dcolors= preview carry them', () => {
    expect(mergeOverrides({ colors: seeds, colors_dark: dark }, null)).toEqual({ colors: seeds, fonts: null, colors_dark: dark })
    expect(mergeOverrides({ colors: seeds }, { colors_dark: dark })?.colors_dark).toEqual(dark)
    const store = new Map<string, string>()
    const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v), removeItem: (k: string) => void store.delete(k) }
    expect(previewOverrides('?dcolors=101820,e8efe9,3ddc97', storage)?.colors_dark).toEqual(dark)
    expect(previewOverrides('?dcolors=off', storage)).toBeNull()
  })
})

describe('paper-brick with own colours (W25-R55)', () => {
  it('the colour rules also apply through a marker on <html>, removed again with the look', () => {
    applyThemeOverrides({ colors: seeds })
    const css = document.getElementById('rs-theme-overrides')!.textContent!
    expect(document.documentElement.dataset.ownColours).toBe('')
    expect(css).toContain('html:not([data-square-theme])[data-own-colours] .ds-scope.ds-scope{')
    expect(css).toContain('--t-accent:#c2410c;')
    applyThemeOverrides({ fonts: 'soft' })
    expect(document.documentElement.dataset.ownColours).toBeUndefined()
    applyThemeOverrides(null)
    expect(document.documentElement.dataset.ownColours).toBeUndefined()
  })
  it('the token map gives paper-brick the colour tokens only, never radius or fonts', () => {
    const map = readFileSync(resolve(process.cwd(), 'src/styles/square-theme-map.css'), 'utf-8')
    const own = map.split('}')[0]!
    expect(own).toContain('html:not([data-square-theme])[data-own-colours] .ds-scope')
    expect(own).not.toMatch(/--ds-radius|--ds-font/)
  })
  it('an own font pair also reaches paper-brick through its own marker, and the console keeps its type', () => {
    applyThemeOverrides({ fonts: 'soft' })
    const css = document.getElementById('rs-theme-overrides')!.textContent!
    expect(document.documentElement.dataset.ownFonts).toBe('')
    expect(css).toContain('html:not([data-square-theme])[data-own-fonts] .ds-scope.ds-scope{--ds-font-display:')
    expect(readFileSync(resolve(process.cwd(), 'src/styles/admin-type.css'), 'utf-8')).toContain('html[data-own-fonts] .ds-appshell')
    applyThemeOverrides(null)
    expect(document.documentElement.dataset.ownFonts).toBeUndefined()
  })
})
