// Tests for fontPairs.ts (3 groups): the list against themes.json, ids, the font stack.
// Run from square/frontend: npx vitest run src/themes/fontPairs.spec.ts
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { FONT_PAIRS, fontPairById, fontStack } from './fontPairs'

const themes = JSON.parse(readFileSync(resolve(process.cwd(), '..', '..', 'design/tenant-themes-v7/themes.json'), 'utf-8')).themes as Array<Record<string, any>>

describe('FONT_PAIRS', () => {
  it('has 23 pairs with unique ids', () => {
    expect(FONT_PAIRS).toHaveLength(23)
    expect(new Set(FONT_PAIRS.map((p) => p.id)).size).toBe(23)
  })
  for (const p of FONT_PAIRS.slice(14)) {
    it(`${p.id}: the address loads ${p.display} and ${p.body}`, () => {
      expect(p.url).toContain(`family=${p.display.replace(/ /g, '+')}`)
      expect(p.url).toContain(`family=${p.body.replace(/ /g, '+')}`)
    })
  }
  for (const p of FONT_PAIRS.slice(0, 14)) {
    it(`${p.id}: some theme uses ${p.display} + ${p.body} with exactly this address`, () => {
      const t = themes.find((x) => x.display === p.display && x.body === p.body)
      expect(t, 'no theme uses this pair').toBeTruthy()
      expect(t!.fonts).toContain(p.url)
    })
  }
})

describe('lookup and stack', () => {
  it('finds a pair by id and returns null for an unknown or empty id', () => {
    expect(fontPairById('soft')?.display).toBe('Quicksand')
    expect(fontPairById('nope')).toBeNull()
    expect(fontPairById(null)).toBeNull()
  })
  it('ends a serif stack in Georgia and a sans stack in Helvetica/Arial', () => {
    expect(fontStack('Lora', true)).toBe('"Lora",Georgia,serif')
    expect(fontStack('Sora', false)).toBe('"Sora","Helvetica Neue",Arial,sans-serif')
  })
})
