// Tests for deriveTokens.ts (3 groups): parity with the generated theme CSS for all 56 themes in both modes, seeds give readable colours, bad input.
// Run from square/frontend: npx vitest run src/themes/deriveTokens.spec.ts
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { contrastRatio, deriveColourTokens, isHex, paletteFromSeeds, type Palette } from './deriveTokens'

const ROOT = resolve(process.cwd(), '..', '..')
const themes = JSON.parse(readFileSync(resolve(ROOT, 'design/tenant-themes-v7/themes.json'), 'utf-8')).themes as Array<Record<string, any>>
const css = readFileSync(resolve(process.cwd(), 'src/styles/square-layout-themes.css'), 'utf-8')

/** The declarations of the block whose selector line starts with `head` (light: `.ds-scope {`, dark: the `html.dark[...]` rule). */
function block(head: string): Record<string, string> {
  const start = css.indexOf(head)
  if (start < 0) throw new Error('block not found: ' + head)
  const open = css.indexOf('{', start)
  const close = css.indexOf('}', open)
  const out: Record<string, string> = {}
  for (const m of css.slice(open + 1, close).matchAll(/(--t-[\w-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim()
  return out
}

function paletteOf(t: Record<string, any>, mode: 'light' | 'dark'): Palette {
  const c = { ...t[mode === 'light' ? 'l' : 'd'] } as Palette
  const extra = t.rth?.[mode]
  if (extra?.acc2) c.acc2 = extra.acc2
  return c
}

describe('parity with build_layout_themes.py', () => {
  it('has 56 themes, 55 of them generated (paper-brick sets nothing)', () => {
    expect(themes).toHaveLength(56)
    expect(css.includes('data-square-theme="paper-brick"')).toBe(false)
  })
  for (const mode of ['light', 'dark'] as const) {
    it(`every colour token of every theme matches the generated CSS (${mode})`, () => {
      const bad: string[] = []
      for (const t of themes) {
        if (t.id === 'paper-brick') continue
        const head = mode === 'light' ? `html[data-square-theme="${t.id}"] .ds-scope {` : `html.dark[data-square-theme="${t.id}"] .ds-scope,`
        const want = block(head)
        const got = deriveColourTokens(paletteOf(t, mode), mode)
        for (const [k, v] of Object.entries(got)) {
          if (want[k]?.toLowerCase() !== v.toLowerCase()) bad.push(`${t.id} ${mode} ${k}: css ${want[k]} / ts ${v}`)
        }
      }
      expect(bad.slice(0, 15)).toEqual([])
    })
  }
})

describe('paletteFromSeeds', () => {
  const seeds = [
    { bg: '#F9F2E8', ink: '#4A3627', acc: '#A8422A' },
    { bg: '#ffffff', ink: '#111111', acc: '#2563eb' },
    { bg: '#0b1020', ink: '#e8ecf5', acc: '#ffcc00' },
    { bg: '#fff3b0', ink: '#fff3b0', acc: '#fff3b0' },
    { bg: '#f0f', ink: '#0f0', acc: '#00f' },
  ]
  for (const s of seeds) {
    for (const mode of ['light', 'dark'] as const) {
      it(`gives readable tokens for ${s.bg}/${s.ink}/${s.acc} (${mode})`, () => {
        const t = deriveColourTokens(paletteFromSeeds(s, mode), mode)
        const grounds = [t['--t-bg'], t['--t-surface'], t['--t-surface-sunken'], t['--t-primary-soft']]
        for (const g of grounds) {
          expect(contrastRatio(t['--t-text-strong'], g)).toBeGreaterThanOrEqual(7)
          expect(contrastRatio(t['--t-text'], g)).toBeGreaterThanOrEqual(4.5)
          expect(contrastRatio(t['--t-link'], g)).toBeGreaterThanOrEqual(4.5)
        }
        expect(contrastRatio(t['--t-on-primary'], t['--t-accent'])).toBeGreaterThanOrEqual(4.5)
      })
    }
  }
})

describe('paletteFromSeeds for a theme that opens dark (seeds describe the dark look)', () => {
  const dark = { bg: '#101014', ink: '#ece8e1', acc: '#ff5a36' }
  it('uses the seeds themselves for the dark look and derives a pale light look from them', () => {
    const d = paletteFromSeeds(dark, 'dark', 'dark')
    expect(d.bg).toBe('#101014')
    expect(d.acc).toBe('#ff5a36')
    const l = paletteFromSeeds(dark, 'light', 'dark')
    expect(contrastRatio('#000000', l.bg)).toBeGreaterThan(contrastRatio('#ffffff', l.bg)) // a light ground
  })
  const sets = [dark, { bg: '#0b1020', ink: '#e8ecf5', acc: '#ffcc00' }, { bg: '#2a0a3a', ink: '#2a0a3a', acc: '#2a0a3a' }, { bg: '#0f0', ink: '#f0f', acc: '#00f' }]
  for (const s of sets) {
    for (const mode of ['light', 'dark'] as const) {
      it(`gives readable tokens for dark seeds ${s.bg}/${s.ink}/${s.acc} (${mode})`, () => {
        const t = deriveColourTokens(paletteFromSeeds(s, mode, 'dark'), mode)
        for (const g of [t['--t-bg'], t['--t-surface'], t['--t-surface-sunken'], t['--t-primary-soft']]) {
          expect(contrastRatio(t['--t-text-strong'], g)).toBeGreaterThanOrEqual(7)
          expect(contrastRatio(t['--t-text'], g)).toBeGreaterThanOrEqual(4.5)
          expect(contrastRatio(t['--t-link'], g)).toBeGreaterThanOrEqual(4.5)
        }
        expect(contrastRatio(t['--t-on-primary'], t['--t-accent'])).toBeGreaterThanOrEqual(4.5)
      })
    }
  }
  it('leaves light-first behaviour as it was: the default seed mode is light', () => {
    const s = { bg: '#F9F2E8', ink: '#4A3627', acc: '#A8422A' }
    expect(paletteFromSeeds(s, 'light')).toEqual(paletteFromSeeds(s, 'light', 'light'))
    expect(paletteFromSeeds(s, 'light').bg).toBe('#F9F2E8')
  })
})

describe('isHex', () => {
  it('accepts #rgb and #rrggbb only', () => {
    expect(isHex('#abc')).toBe(true)
    expect(isHex('#A8422A')).toBe(true)
    expect(isHex('red')).toBe(false)
    expect(isHex('#12345')).toBe(false)
  })
})
