// Scoped theme tests (run: npm run test:themes).
//  1. No theme CSS contains NaN (the tenant export ships invalid #xxxxNaN hover/press values; we recompute them).
//  2. The theme contract: every theme has light and dark blocks that define every --t-* variable of the design contract.
//  3. Structure options in src/themes/index.ts (what components render) equal the structure tokens in themes.css.
//  4. Platform mode and tenant mode are independent: platform light + tenant dark and the reverse, for every theme.
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { test } from 'node:test'
import { ALL_THEMES, COMING_THEMES, ENABLED_THEME_IDS, LEGACY_THEMES, THEMES, getTheme, isThemeId } from '@rootsquares/ui/themes'
import { parseRules, resolve } from './cascade.mjs'

const styles = new URL('../platform/src/styles/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const uiStyles = new URL('../ui/src/styles/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1') // the shared design system (ADR 084)
const design = new URL('../../design/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const IDS = ALL_THEMES.map((t) => t.id)
const stripComments = (css) => css.replace(/\/\*[\s\S]*?\*\//g, '')

test('no theme CSS in the app contains NaN', () => {
  const files = [...readdirSync(styles), ...readdirSync(uiStyles)].filter((f) => f.endsWith('.css'))
  assert.ok(files.includes('themes.css'))
  const bad = files.filter((f) => /NaN/.test(stripComments(readFileSync(join(readdirSync(styles).includes(f) ? styles : uiStyles, f), 'utf8'))))
  assert.deepEqual(bad, [])
})

const tenant = parseRules(join(styles, 'themes.css'))
const wrapper = (theme, dark) => ({ tag: 'div', attrs: { 'data-theme': theme, 'data-mode': dark ? 'dark' : 'light' } })
const tokenOf = (theme, dark, name) => resolve([tenant], [wrapper(theme, dark)])[name]

test('every theme defines the full --t-* contract in light and dark', () => {
  const contract = JSON.parse(readFileSync(join(design, 'tenant-themes-v2', 'tokens.json'), 'utf8')).contract
  assert.ok(contract.length > 40, 'contract list read from the design export')
  for (const id of IDS) {
    for (const dark of [false, true]) {
      const props = resolve([tenant], [wrapper(id, dark)])
      const missing = contract.filter((k) => props[k] === undefined || props[k] === '')
      assert.deepEqual(missing, [], `${id} ${dark ? 'dark' : 'light'} is missing ${missing.join(', ')}`)
    }
  }
})

test('structure options in themes/index.ts match the structure tokens in themes.css', () => {
  assert.deepEqual(ALL_THEMES.map((t) => t.id), IDS)
  for (const t of ALL_THEMES) {
    for (const dark of [false, true]) {
      assert.equal(tokenOf(t.id, dark, '--t-header'), t.header, `${t.id} header`)
      assert.equal(tokenOf(t.id, dark, '--t-hero'), t.hero, `${t.id} hero`)
      assert.equal(tokenOf(t.id, dark, '--t-events'), t.events, `${t.id} events`)
      assert.equal(tokenOf(t.id, dark, '--t-image-shape'), t.img, `${t.id} image shape`)
      assert.equal(tokenOf(t.id, dark, '--t-hero-flip'), t.flip ? '1' : '0', `${t.id} flip`)
    }
  }
})

test('56 themes are kept; 18 structures are offered (W18-R25), the rest are legacy, valid for squares already on them; the backend default offers the same ids', () => {
  assert.equal(ALL_THEMES.length, 56)
  assert.ok(ENABLED_THEME_IDS.includes('paper-brick'))
  assert.equal(ENABLED_THEME_IDS.length, 18)
  assert.deepEqual(THEMES.map((t) => t.id), IDS.filter((i) => ENABLED_THEME_IDS.includes(i)))
  assert.equal(THEMES.length + LEGACY_THEMES.length, 56)
  assert.ok(LEGACY_THEMES.every((t) => !ENABLED_THEME_IDS.includes(t.id)))
  assert.equal(COMING_THEMES.length, 0)
  // a retired theme still has a name and is a known id, so a square on it shows and renders
  assert.equal(getTheme('stillwater')?.name, ALL_THEMES.find((t) => t.id === 'stillwater')?.name)
  assert.ok(isThemeId('stillwater') && !isThemeId('nope'))
  const config = readFileSync(new URL('../../backend/app/shared/config.py', import.meta.url), 'utf8')
  const backend = /ENABLED_THEME_IDS: str = "([^"]+)"/.exec(config)?.[1].split(',')
  assert.deepEqual(backend, ENABLED_THEME_IDS)
})

test('the offered structures are three in each of the six families, paper-brick counted in the top bar (W18-R25)', () => {
  const count = {}
  for (const t of THEMES) count[t.shell] = (count[t.shell] ?? 0) + 1
  assert.deepEqual(count, { bar: 3, mast: 3, side: 3, right: 3, tabs: 3, dock: 3 })
  const config = readFileSync(new URL('../../backend/app/shared/config.py', import.meta.url), 'utf8')
  assert.ok(config.includes('sage-round') && !config.includes('fjord-grid'))
})

// Platform side: <html data-brand="brass"> (light) or with data-theme="dark".
const platform = parseRules(join(uiStyles, 'brass.css'))
const html = (dark) => ({ tag: 'html', root: true, attrs: dark ? { 'data-brand': 'brass', 'data-theme': 'dark' } : { 'data-brand': 'brass' } })
const PLATFORM_BG = { light: '#f4efe4', dark: '#14120f' } // --color-bg in export/tokens.css

test('platform light + tenant dark, and the reverse, are independent', () => {
  for (const theme of IDS) {
    const lightBg = tokenOf(theme, false, '--t-bg')
    const darkBg = tokenOf(theme, true, '--t-bg')
    assert.ok(lightBg && darkBg && lightBg !== darkBg, `${theme}: light and dark tenant backgrounds must exist and differ`)
    for (const [platformDark, tenantDark] of [[false, true], [true, false], [false, false], [true, true]]) {
      const props = resolve([platform, tenant], [html(platformDark), wrapper(theme, tenantDark)])
      assert.equal(props['--color-bg'], PLATFORM_BG[platformDark ? 'dark' : 'light'], `${theme}: platform bg follows only the platform mode`)
      assert.equal(props['--t-bg'], tenantDark ? darkBg : lightBg, `${theme}: tenant bg follows only the tenant mode`)
    }
  }
})

test('tenant attributes never match the platform dark selector', () => {
  for (const theme of IDS) {
    const props = resolve([platform, tenant], [html(false), wrapper(theme, true)])
    assert.equal(props['--color-text'], '#1c1a16')
    assert.equal(props['--color-surface'], '#fbf8f0')
  }
})

test('the platform never sets --t-* variables and tenant CSS never sets platform variables', () => {
  const t = tenant.flatMap((r) => Object.keys(r.decls))
  const p = platform.flatMap((r) => Object.keys(r.decls))
  assert.deepEqual(t.filter((k) => !k.startsWith('--t-')), [], 'tenant themes only define --t-* variables')
  assert.deepEqual(p.filter((k) => k.startsWith('--t-')), [], 'platform tokens define no --t-* variables')
})
