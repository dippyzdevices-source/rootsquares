// Tests for the 54 spinners (themes/spinnerArt.ts, styles/spinner-sets.css, BaseSpinner.vue, utils/spinner.ts): the data, the keyframes and colours, drawing one, and the square's kept set.
// Run from square/frontend: npx vitest run src/themes/spinnerArt.spec.ts
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BaseSpinner from '../components/ui/BaseSpinner.vue'
import { ALL_SPINNER_IDS, SPINNER_VARIANTS, isSpinnerId, randomSpinnerVariant } from '../utils/spinner'
import { SPINNER_ART, SPINNER_OCCASIONS } from './spinnerArt'

const css = readFileSync(resolve(process.cwd(), 'src/styles/spinner-sets.css'), 'utf-8')

describe('the spinners (generated data)', () => {
  it('are six occasions of nine, with unique ids; the festival set is the one a square without a choice uses', () => {
    expect(SPINNER_ART).toHaveLength(54)
    expect(new Set(SPINNER_ART.map((a) => a.id)).size).toBe(54)
    expect(SPINNER_OCCASIONS.map((o) => o.name)).toEqual(['Festivals', 'Religious', 'Cultural', 'Bands & Artists', 'Charity & Donations', 'Random Events'])
    expect(SPINNER_ART.filter((a) => a.set === 'Festivals').map((a) => a.id)).toEqual([...SPINNER_VARIANTS])
    for (const o of SPINNER_OCCASIONS) expect(SPINNER_ART.filter((a) => a.set === o.name), o.name).toHaveLength(9)
    expect(ALL_SPINNER_IDS).toHaveLength(54)
  })
  it('are plain drawing: one SVG each, nothing that runs, no template placeholder left', () => {
    for (const a of SPINNER_ART) {
      expect(a.svg.startsWith('<svg') && a.svg.endsWith('</svg>'), a.id).toBe(true)
      expect(a.svg, a.id).not.toMatch(/<script|\son[a-z]+\s*=|javascript:|<foreignObject|<iframe|<image|href=|\{\{|sc-for/i)
      expect(a.name && a.desc, a.id).toBeTruthy()
    }
  })
  it('use only the colour and size variables the stylesheet sets, and every animation has its keyframes', () => {
    const allowed = new Set(['--bg', '--c1', '--c2', '--c3', '--ink', '--sz', '--track'])
    const defined = new Set([...css.matchAll(/@keyframes (sp-[a-z0-9]+)/g)].map((m) => m[1]))
    for (const a of SPINNER_ART) {
      for (const m of a.svg.matchAll(/var\((--[a-z0-9-]+)/g)) expect(allowed.has(m[1]), `${a.id} ${m[1]}`).toBe(true)
      for (const m of a.svg.matchAll(/animation:(sp-[a-z0-9]+)/g)) expect(defined.has(m[1]), `${a.id} ${m[1]}`).toBe(true)
    }
  })
  it('came out of the four loops of the design file expanded: the equalizer has five bars, the confetti eight, the mala twelve beads, the rangoli nine dots', () => {
    const count = (id: string, tag: string) => (SPINNER_ART.find((a) => a.id === id)!.svg.match(new RegExp(`<${tag}[ >]`, 'g')) ?? []).length
    expect(count('equalizer', 'rect')).toBe(5)
    expect(count('confetti', 'rect')).toBe(8)
    expect(count('mala', 'circle')).toBeGreaterThanOrEqual(12)
    expect(count('rangoli', 'circle')).toBe(9)
  })
})

describe('the colours of a spinner (spinner-sets.css)', () => {
  it('give the main colour of the theme, derive the second and third from it where the browser can, and have a dark and a muted tone', () => {
    expect(css).toContain('.rs-spinner-art {')
    expect(css).toContain('--c1: var(--ds-action-primary)')
    expect(css).toMatch(/@supports \(color: oklch\(from red l c h\)\)/)
    expect(css).toContain('--c2: oklch(from var(--c1)')
    expect(css).toContain('--c3: oklch(from var(--c1)')
    expect(css).toContain('.rs-spinner-art--dark {')
    expect(css).toContain('.rs-spinner-art--muted {')
  })
})

describe('BaseSpinner', () => {
  it('draws the SVG of the variant at the size asked, in the sizes of the design system and the 96 px of the Spinner Sets design', () => {
    const w = mount(BaseSpinner, { props: { variant: 'diya', size: 'lg' } })
    expect(w.find('.rs-spinner-art svg').exists()).toBe(true)
    expect(w.find('.rs-spinner-art').attributes('style')).toContain('--sz: 40px')
    expect(w.attributes('role')).toBe('status')
    for (const [size, px] of [['sm', 16], ['md', 24], ['lg', 40], ['xl', 56], ['xxl', 96]] as const) {
      expect(mount(BaseSpinner, { props: { variant: 'kite', size } }).find('.rs-spinner-art').attributes('style'), size).toContain(`--sz: ${px}px`)
    }
  })
  it('draws the festival set from the same art and falls back to the ring for an unknown id', () => {
    for (const v of SPINNER_VARIANTS) expect(mount(BaseSpinner, { props: { variant: v } }).find('.rs-spinner-art svg').exists(), v).toBe(true)
    const ring = mount(BaseSpinner, { props: { variant: 'ring' } }).html()
    expect(mount(BaseSpinner, { props: { variant: 'nope' } }).html()).toBe(ring)
  })
  it('takes the dark and the muted tone as a class', () => {
    expect(mount(BaseSpinner, { props: { variant: 'vinyl', tone: 'on-dark' } }).find('.rs-spinner-art').classes()).toContain('rs-spinner-art--dark')
    expect(mount(BaseSpinner, { props: { variant: 'vinyl', tone: 'muted' } }).find('.rs-spinner-art').classes()).toContain('rs-spinner-art--muted')
    expect(mount(BaseSpinner, { props: { variant: 'vinyl' } }).find('.rs-spinner-art').classes()).toEqual(['rs-spinner-art'])
  })
})

describe('randomSpinnerVariant with the square\'s kept set', () => {
  it('picks from the kept spinners, leaves out ids it does not know, and falls back to the festival set when nothing is kept', () => {
    expect(randomSpinnerVariant(['diya'])).toBe('diya')
    expect(randomSpinnerVariant(['nope', 'kite'])).toBe('kite')
    expect(randomSpinnerVariant(['nope'], () => 0)).toBe(SPINNER_VARIANTS[0])
    expect(SPINNER_VARIANTS).toContain(randomSpinnerVariant(null))
    expect(SPINNER_VARIANTS).toContain(randomSpinnerVariant([]))
    const seen = new Set(Array.from({ length: 40 }, (_, i) => randomSpinnerVariant(['diya', 'kite', 'ring'], () => (i % 3) / 3)))
    expect(seen).toEqual(new Set(['diya', 'kite', 'ring']))
    expect(isSpinnerId('mehndi') && isSpinnerId('dhak') && !isSpinnerId('nope')).toBe(true)
  })
})
