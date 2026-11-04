// Tests for layouts (12 cases), e.g. layout themes (W9-R5); has the 16 reference layouts and the 39 engine themes, none for the de; maps each reference theme to the shell / hero / variants of its layout.
/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LAYOUT_THEME_FONT_URLS } from '../themes/layoutThemeFonts'
import { ENGINES, LAYOUTS } from './layouts'

const IDS = ['terracotta-hall',  'hush-pond',  'fjord-grid',  'pencil-notebook',  'linen-arch',  'berry-panel',  'ledger-gazette',  'marquee-showbill',  'canopy-leaf',  'clay-press',  'dune-teal',  'pearl-emboss',  'product-console',  'daylight-agenda',  'torn-kraft',  'sage-round']
const ENGINE_IDS = ['harvest-hall',  'stillwater',  'fjord-modern',  'pencil-club',  'olive-linen',  'berry-courtyard',  'atrium',  'ledger',  'marquee',  'canopy-grove',  'softform',  'daylight',  'sage-cafe',  'japandi-atelier',  'clay-pastel',  'sand-teal',  'pearl',  'product',  'torn-paper',  'verdeo',  'tidewater',  'mela-noir',  'lotus-hour',  'fuchsia-pop',  'kash-meadow',  'cacao-mint',  'garnet-pearl',  'denim-linen',  'orchid-dusk',  'neon-cyan',  'lime-fizz',  'olive-press',  'peach-charcoal',  'citrus-night',  'bone-forest',  'ruby-pop',  'mint-night',  'pewter',  'cobalt-pop']
const ids56 = ['harvest-hall',  'stillwater',  'fjord-modern',  'pencil-club',  'olive-linen',  'berry-courtyard',  'atrium',  'ledger',  'marquee',  'canopy-grove',  'softform',  'daylight',  'sage-cafe',  'japandi-atelier',  'clay-pastel',  'sand-teal',  'pearl',  'product',  'torn-paper',  'verdeo',  'tidewater',  'mela-noir',  'lotus-hour',  'fuchsia-pop',  'kash-meadow',  'cacao-mint',  'garnet-pearl',  'denim-linen',  'orchid-dusk',  'neon-cyan',  'lime-fizz',  'olive-press',  'peach-charcoal',  'citrus-night',  'bone-forest',  'ruby-pop',  'mint-night',  'pewter',  'cobalt-pop',  'terracotta-hall',  'hush-pond',  'fjord-grid',  'pencil-notebook',  'linen-arch',  'berry-panel',  'ledger-gazette',  'marquee-showbill',  'canopy-leaf',  'clay-press',  'dune-teal',  'pearl-emboss',  'product-console',  'daylight-agenda',  'torn-kraft',  'sage-round']
const css = readFileSync(resolve(process.cwd(), 'src/styles/square-layout-themes.css'), 'utf-8') // vitest runs from square/frontend

describe('layout themes (W9-R5)', () => {
  it('has the 16 reference layouts and the 39 engine themes, none for the default look', () => {
    expect(Object.keys(LAYOUTS)).toEqual(IDS)
    expect(Object.keys(ENGINES)).toEqual(ENGINE_IDS)
    expect(Object.keys(LAYOUT_THEME_FONT_URLS)).toEqual([...IDS, ...ENGINE_IDS].sort((a, b) => ids56.indexOf(a) - ids56.indexOf(b)))
    expect(LAYOUTS['paper-brick']).toBeUndefined()
    expect(ENGINES['paper-brick']).toBeUndefined()
  })

  it('maps each reference theme to the shell / hero / variants of its layout', () => {
    const row = (id: string) => { const l = LAYOUTS[id]!; return [l.shell, l.hero, l.ev, l.gal, l.news, l.her, l.mem, l.con].join(' / ') }
    expect(row('terracotta-hall')).toBe('harvest / asym / list / masonry / lead / years / cards / split')
    expect(row('hush-pond')).toBe('still / quiet / timeline / film / index / essay / rows / letter')
    expect(row('fjord-grid')).toBe('fjord / swiss / cards / mosaic / cols / years / band / split')
    expect(row('pencil-notebook')).toBe('pencil / zine / notes / polaroid / cards / essay / cards / card')
    expect(row('linen-arch')).toBe('olive / arch / cards / feature / cards / stack / cards / card')
    expect(row('berry-panel')).toBe('berry / berry / media / uniform / lead / years / rows / split')
    expect(row('ledger-gazette')).toBe('ledger / front / table / uniform / cols / essay / rows / letter')
    expect(row('marquee-showbill')).toBe('marquee / giant / giant / film / index / stack / band / letter')
    expect(row('canopy-leaf')).toBe('canopy / leaf / tiles / mosaic / cards / years / cards / card')
    expect(row('clay-press')).toBe('clay / softgrid / neu / framed / cards / stack / cards / card')
    expect(row('dune-teal')).toBe('sand / emboss / neu / framed / cards / years / cards / card')
    expect(row('pearl-emboss')).toBe('pearl / pearl / neu / framed / cards / stack / cards / card')
    expect(row('product-console')).toBe('product / product / datarows / mosaic / cards / years / cards / split')
    expect(row('daylight-agenda')).toBe('daylight / daylight / agenda / framed / cards / stack / cards / card')
    expect(row('torn-kraft')).toBe('torn / torn / strip / film / lead / essay / band / letter')
    expect(row('sage-round')).toBe('cafe / cafe / round / masonry / cards / stack / cards / split')
  })

  it('has a light and a dark block for every theme and no invalid value', () => {
    for (const id of ids56) {
      expect(css).toContain(`html[data-square-theme="${id}"] .ds-scope {`)
      expect(css).toContain(`html.dark[data-square-theme="${id}"] .ds-scope,`)
    }
    expect(css).not.toContain('NaN')
    expect(css.match(/--t-bg:/g)).toHaveLength(110)
  })
})

// The module rules read the square's module list when the file is loaded, so each case loads it afresh with its own list.
async function loadWith(modules: string[]) {
  vi.resetModules()
  vi.doMock('../services/squareConfig', () => ({ squareProfile: { name: 'Test Square', slug: 't', themeId: 'terracotta-hall', currency: 'NOK', modules }, squareAuth: null }))
  return import('./useSiteLayout')
}

describe('module rules of the themed site', () => {
  afterEach(() => vi.doUnmock('../services/squareConfig'))

  it('shows every page and the member button when all modules are on', async () => {
    const m = await loadWith(['events', 'gallery', 'news', 'memberships'])
    expect(m.navItems.map((n) => n.key)).toEqual(['home', 'events', 'heritage', 'gallery', 'membership', 'news', 'contact'])
    expect(m.cta).toEqual({ label: 'Become a member', to: '/membership' })
    expect(m.cta2).toEqual({ label: 'See the programme', to: '/events' })
  })

  it('removes the link of a module that is off and reflows the rest', async () => {
    const m = await loadWith(['events', 'news', 'memberships'])
    expect(m.navItems.map((n) => n.key)).toEqual(['home', 'events', 'heritage', 'membership', 'news', 'contact'])
    expect(m.sectionOn('gallery')).toBe(false)
  })

  it('adds Donate with the Donations module, and Newsletter only when News is off', async () => {
    const withNews = await loadWith(['news', 'newsletter', 'donations'])
    expect(withNews.navItems.map((n) => n.key)).toEqual(['home', 'heritage', 'news', 'contact', 'donate'])
    const noNews = await loadWith(['newsletter', 'donations'])
    expect(noNews.navItems.map((n) => n.key)).toEqual(['home', 'heritage', 'contact', 'donate', 'newsletter'])
  })

  it('Membership off: Become a member turns into Get in touch', async () => {
    const m = await loadWith(['events', 'gallery'])
    expect(m.cta).toEqual({ label: 'Get in touch', to: '/contact' })
    expect(m.navItems.some((n) => n.key === 'membership')).toBe(false)
  })

  it('Events off: the second button falls back to Heritage', async () => {
    const m = await loadWith(['gallery', 'memberships'])
    expect(m.cta2).toEqual({ label: 'Our story', to: '/about' })
  })

  it('minimal: only Home, Heritage and Contact remain, and the buttons still lead somewhere', async () => {
    const m = await loadWith([])
    expect(m.navItems.map((n) => n.key)).toEqual(['home', 'heritage', 'contact'])
    expect(m.cta.to).toBe('/contact')
    expect(m.cta2.to).toBe('/about')
  })

  it('splits a headline in three with the middle part emphasised', async () => {
    const m = await loadWith([])
    expect(m.headlineParts('Bengal kept alive in Oslo')).toEqual(['Bengal', 'kept alive in', 'Oslo'])
    expect(m.headlineParts('Bengal kept alive')).toEqual(['Bengal', 'kept', 'alive'])
    expect(m.headlineParts('Two words')).toEqual(['Two', 'words', ''])
    expect(m.headlineParts('BCA')).toEqual(['BCA', '', ''])
    expect(m.headlineParts('  ')).toEqual(['', '', ''])
  })
})
