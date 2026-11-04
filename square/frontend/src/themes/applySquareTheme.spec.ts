// Tests for applySquareTheme (5 cases), e.g. square themes (W9-R10); covers the 55 non-default themes in light and dark; every token the mapping reads is defined in every theme block.
/// <reference types="node" />
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { applySquareTheme, squareThemeFontsUrl } from './applySquareTheme'
import { LAYOUT_THEME_FONT_URLS } from './layoutThemeFonts'

const css = readFileSync(resolve(process.cwd(), 'src/styles/square-layout-themes.css'), 'utf-8') // vitest runs from square/frontend
const mapping = readFileSync(resolve(process.cwd(), 'src/styles/square-theme-map.css'), 'utf-8')
const ids = Object.keys(LAYOUT_THEME_FONT_URLS)

describe('square themes (W9-R10)', () => {
  it('covers the 55 non-default themes in light and dark', () => {
    expect(ids).toHaveLength(55)
    expect(ids).not.toContain('paper-brick')
    for (const id of ids) {
      expect(css).toContain(`html[data-square-theme="${id}"] .ds-scope {`)
      expect(css).toContain(`html.dark[data-square-theme="${id}"] .ds-scope,`)
      expect(css).toContain(`html[data-square-theme="${id}"] .ds-scope.ds-force-dark {`)
    }
    expect(css).not.toContain('NaN')
  })

  it('every token the mapping reads is defined in every theme block', () => {
    const used = new Set<string>(mapping.match(/var\((--t-[a-z0-9-]+)\)/g)?.map((v: string) => v.slice(4, -1)) ?? [])
    const all = css.split(/\r?\n\r?\n/).filter((b: string) => b.startsWith('html'))
    const blocks = all.filter((b: string) => b.split('{')[0]!.includes('.ds-scope'))
    expect(blocks).toHaveLength(110)
    for (const block of blocks) for (const token of used) expect(block.includes(`${token}:`), token).toBe(true)
  })

  it('every theme and mode also has the Tailwind colour bridge and the component knobs (W10-R6)', () => {
    const all = css.split(/\r?\n\r?\n/).filter((b: string) => b.startsWith('html'))
    const bridges = all.filter((b: string) => !b.split('{')[0]!.includes('.ds-scope'))
    expect(bridges).toHaveLength(110)
    for (const block of bridges) for (const token of ['--color-bg', '--color-surface', '--color-primary', '--color-text', '--color-on-secondary', '--font-sans']) expect(block.includes(`${token}:`), token).toBe(true)
    const scoped = all.filter((b: string) => b.split('{')[0]!.includes('.ds-scope'))
    for (const block of scoped) for (const token of ['--t-input-radius', '--t-btn-case', '--t-tab-family', '--t-badge-case', '--t-nav-radius']) expect(block.includes(`${token}:`), token).toBe(true)
  })

  it('applies a known theme once and ignores the default and unknown ids', () => {
    const doc = document.implementation.createHTMLDocument('t')
    expect(applySquareTheme('paper-brick', doc)).toBe(false)
    expect(applySquareTheme('nope', doc)).toBe(false)
    expect(doc.documentElement.dataset.squareTheme).toBeUndefined()
    expect(applySquareTheme('stillwater', doc)).toBe(true)
    expect(applySquareTheme('stillwater', doc)).toBe(true)
    expect(doc.documentElement.dataset.squareTheme).toBe('stillwater')
    expect(doc.querySelectorAll('link[data-square-theme-fonts]')).toHaveLength(1)
    expect(squareThemeFontsUrl('stillwater')).toContain('family=Cormorant+Garamond')
  })
})
