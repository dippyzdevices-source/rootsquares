// Tests that the 16 theme-based and the 10 own ready-made colour schemes of the platform's Theme page (frontend/platform/src/themes/lookPresets.ts, W18-R26) stay readable once derived: each scheme's page, text and accent colours,
// read as a structure that opens light and as one that opens dark, give strong text 7:1, text and muted text 4.5:1 and a readable button label, in light and in dark mode.
// Run from square/frontend: npx vitest run src/themes/colourSchemes.spec.ts
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { contrastRatio, deriveColourTokens, paletteFromSeeds, type Mode } from './deriveTokens'

const root = resolve(process.cwd(), '../..')
const themes = JSON.parse(readFileSync(resolve(root, 'design/tenant-themes-v7/themes.json'), 'utf-8')).themes as { id: string; mode: Mode; l: Record<string, string>; d: Record<string, string> }[]
const lookPresets = readFileSync(resolve(root, 'frontend/platform/src/themes/lookPresets.ts'), 'utf-8')
const block = lookPresets.slice(lookPresets.indexOf('COLOUR_SCHEMES: {'), lookPresets.indexOf('\n]', lookPresets.indexOf('COLOUR_SCHEMES: {')))
const ownBlock = lookPresets.slice(lookPresets.indexOf('export const OWN_SCHEMES'), lookPresets.indexOf('export const ALL_SCHEMES'))
const own = [...ownBlock.matchAll(/\{ id: '([a-z-]+)', name: '[^']+', l: \['(#[0-9a-f]{6})', '(#[0-9a-f]{6})', '(#[0-9a-f]{6})'\], d: \['(#[0-9a-f]{6})', '(#[0-9a-f]{6})', '(#[0-9a-f]{6})'\] \}/g)].map((m) => ({ id: m[1]!, l: { bg: m[2]!, ink: m[3]!, acc: m[4]! }, d: { bg: m[5]!, ink: m[6]!, acc: m[7]! } }))
const ids = [...block.matchAll(/\{ id: '([a-z-]+)', name:/g)].map((m) => m[1])

describe('the 16 theme-based colour schemes', () => {
  it('are 16 themes of themes.json', () => {
    expect(ids).toHaveLength(16)
    for (const id of ids) expect(themes.some((t) => t.id === id), id).toBe(true)
  })
  for (const seedMode of ['light', 'dark'] as Mode[]) {
    it(`stay readable in light and dark when read as a structure that opens ${seedMode}`, () => {
      for (const id of ids) {
        const t = themes.find((x) => x.id === id)!
        const c = seedMode === 'dark' ? t.d : t.l // what presetColours() gives the card: the theme's palette in the structure's own mode
        const seeds = { bg: c.bg.toLowerCase(), ink: c.ink.toLowerCase(), acc: c.acc.toLowerCase() }
        for (const mode of ['light', 'dark'] as Mode[]) {
          const tk = deriveColourTokens(paletteFromSeeds(seeds, mode, seedMode), mode)
          const where = `${id} ${seedMode}-first, ${mode}`
          for (const ground of ['--t-bg', '--t-surface', '--t-surface-sunken']) {
            expect(contrastRatio(tk['--t-text-strong'], tk[ground]), `${where}: strong text on ${ground}`).toBeGreaterThanOrEqual(7)
            expect(contrastRatio(tk['--t-text'], tk[ground]), `${where}: text on ${ground}`).toBeGreaterThanOrEqual(4.5)
            expect(contrastRatio(tk['--t-text-muted'], tk[ground]), `${where}: muted text on ${ground}`).toBeGreaterThanOrEqual(4.5)
          }
          expect(contrastRatio(tk['--t-on-primary'], tk['--t-accent']), `${where}: button label`).toBeGreaterThanOrEqual(4.5)
        }
      }
    })
  }
})

describe('the 10 own colour sets (W25-R62)', () => {
  it('are ten', () => expect(own).toHaveLength(10))
  for (const seedMode of ['light', 'dark'] as Mode[]) {
    it(`stay readable in light and dark when read as a structure that opens ${seedMode}`, () => {
      for (const o of own) {
        const seeds = seedMode === 'dark' ? o.d : o.l
        for (const mode of ['light', 'dark'] as Mode[]) {
          const tk = deriveColourTokens(paletteFromSeeds(seeds, mode, seedMode), mode)
          const where = `${o.id} ${seedMode}-first, ${mode}`
          for (const ground of ['--t-bg', '--t-surface', '--t-surface-sunken']) {
            expect(contrastRatio(tk['--t-text-strong'], tk[ground]), `${where}: strong text on ${ground}`).toBeGreaterThanOrEqual(7)
            expect(contrastRatio(tk['--t-text'], tk[ground]), `${where}: text on ${ground}`).toBeGreaterThanOrEqual(4.5)
            expect(contrastRatio(tk['--t-text-muted'], tk[ground]), `${where}: muted text on ${ground}`).toBeGreaterThanOrEqual(4.5)
          }
          expect(contrastRatio(tk['--t-on-primary'], tk['--t-accent']), `${where}: button label`).toBeGreaterThanOrEqual(4.5)
        }
      }
    })
  }
})
