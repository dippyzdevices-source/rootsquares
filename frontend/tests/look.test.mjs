// Scoped tests of the own-look choices (run: npm run test:look; W18-R19): the 23 font pairs equal the square app's list and the backend's ids,
// the 25 colour schemes name themes that exist with three hex colours, the platform's language file has every key the card uses.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { seasonActive } from '../platform/src/themes/seasons.ts'

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf-8')
const presets = read('../platform/src/themes/lookPresets.ts')
const pairRe = /\{ id: '([a-z]+)', label: '([^']+)', display: '([^']+)', body: '([^']+)'/g

test('the font pairs equal the square app list and the backend ids', () => {
  const mine = [...presets.matchAll(pairRe)].map((m) => m.slice(1, 5).join('|'))
  const theirs = [...read('../../square/frontend/src/themes/fontPairs.ts').matchAll(pairRe)].map((m) => m.slice(1, 5).join('|'))
  assert.equal(mine.length, 23)
  assert.deepEqual(mine, theirs)
  const backend = read('../../backend/app/platform/theme_overrides.py')
  const ids = [...backend.slice(backend.indexOf('FONT_PAIR_IDS'), backend.indexOf('COLOR_KEYS')).matchAll(/"([a-z]+)"/g)].map((m) => m[1])
  assert.deepEqual(ids, mine.map((x) => x.split('|')[0]))
})

test('the theme-based colour schemes are 16 themes that exist, each with its own colour name and its own three light and dark colours (W18-R26, W25-R62)', () => {
  const from = presets.indexOf('COLOUR_SCHEMES: {')
  const block = presets.slice(from, presets.indexOf('\n]', from))
  const schemes = [...block.matchAll(/\{ id: '([a-z-]+)', name: '([^']+)' \}/g)].map((m) => ({ id: m[1], name: m[2] }))
  assert.equal(schemes.length, 16)
  assert.equal(new Set(schemes.map((s) => s.id)).size, 16, 'no theme twice')
  assert.equal(new Set(schemes.map((s) => s.name)).size, 16, 'no name twice')
  const colors = read('../platform/src/themes/colors.ts')
  const seen = new Set()
  for (const { id } of schemes) {
    const at = colors.indexOf(`"${id}": {`)
    assert.ok(at > 0, `${id} is in colors.ts`)
    const part = colors.slice(at, at + 900)
    for (const mode of ['light', 'dark']) {
      const m = part.match(new RegExp(`"${mode}": \\{ "bg": "(#[0-9A-Fa-f]{6})", "ink": "(#[0-9A-Fa-f]{6})", "accent": "(#[0-9A-Fa-f]{6})"`))
      assert.ok(m, `${id} has ${mode} bg, ink and accent`)
      if (mode === 'light') {
        const key = m.slice(1, 4).join('|').toLowerCase()
        assert.ok(!seen.has(key), `${id} repeats another scheme's colours`)
        seen.add(key)
      }
    }
  }
})

test('the Theme page card has every language key it uses', () => {
  const en = { ...JSON.parse(read('../ui/src/i18n/en.json')), ...JSON.parse(read('../platform/src/i18n/en.json')) } // the shared messages and the customer-only ones (lockedLook, W26-R13)
  const card = read('../platform/src/features/portal/ThemeLookCard.vue') + read('../platform/src/features/portal/SpinnerPicker.vue') + read('../platform/src/features/portal/ThemeDraftPanel.vue') + read('../platform/src/features/portal/ThemeSeasonsPanel.vue')
  const keys = new Set([...card.matchAll(/\bt\('([a-zA-Z.]+)'/g)].map((m) => m[1]))
  for (const k of ['spinnersSetAll', 'spinnersSetNone']) keys.add('portal.theme.look.' + k) // chosen by a condition in the picker
  assert.ok(keys.size > 8, 'the card uses its own keys')
  for (const k of keys) assert.equal(typeof k.split('.').reduce((o, p) => o?.[p], en), 'string', k)
  // keys the card builds from a pattern (the three colour labels, and the dark-look variants for a theme that opens dark)
  for (const k of ['bg', 'ink', 'acc', 'bgHex', 'inkHex', 'accHex', 'bgDark', 'inkDark', 'accDark', 'readableDark']) assert.equal(typeof en.portal.theme.look[k], 'string', k)
})

test('the platform spinner list equals the square app list and the backend ids; the recommended occasions exist (W18-R28, R29)', () => {
  const ids = (src) => [...src.matchAll(/"id": "([a-z-]+)"/g)].map((m) => m[1])
  const mine = read('../platform/src/themes/spinnerSets.ts')
  const art = ids(mine.slice(0, mine.indexOf('SPINNER_OCCASIONS')))
  const theirs = ids(read('../../square/frontend/src/themes/spinnerArt.ts'))
  assert.equal(art.length, 54)
  assert.deepEqual(art, theirs)
  assert.deepEqual(art.slice(0, 9), ['ring', 'chakra', 'dhak', 'shankha', 'lantern', 'holi', 'sparkler', 'pongal-pot', 'sunrise'])
  const backend = [...read('../../backend/app/platform/spinner_ids.py').matchAll(/^ {4}"([a-z-]+)",$/gm)].map((m) => m[1])
  assert.deepEqual(backend, art)
  const occasions = [...mine.slice(mine.indexOf('SPINNER_OCCASIONS')).matchAll(/"name": "([^"]+)"/g)].map((m) => m[1])
  assert.deepEqual(occasions, ['Festivals', 'Religious', 'Cultural', 'Bands & Artists', 'Charity & Donations', 'Random Events'])
  const rec = presets.slice(presets.indexOf('SPINNER_RECOMMENDED'))
  const kinds = [...rec.matchAll(/^ {2}([a-z]+): \[([^\]]+)\]/gm)].map((m) => [m[1], [...m[2].matchAll(/'([^']+)'/g)].map((x) => x[1])])
  assert.deepEqual(kinds.map((k) => k[0]), ['cultural', 'religious', 'band', 'charity'])
  for (const [, names] of kinds) for (const n of names) assert.ok(occasions.includes(n), n)
  // every kind of group of the platform has a recommendation
  const sets = read('../../backend/app/platform/starter_sets.py')
  assert.deepEqual([...sets.matchAll(/^ {4}StarterSet\(\r?\n {8}"([a-z]+)",/gm)].map((m) => m[1]), kinds.map((k) => k[0]))
})

test('the shape options equal the backend lists and the square app tables (W18 shapes step 7)', () => {
  const backend = read('../../backend/app/platform/theme_overrides.py')
  const square = read('../../square/frontend/src/themes/shapes.ts')
  const from = presets.indexOf('export const SHAPE_PARTS')
  const block = presets.slice(from, presets.indexOf('export type ShapeLookChoice'))
  for (const part of ['buttons', 'cards', 'photos', 'edges']) {
    const mine = [...block.slice(block.indexOf(`id: '${part}'`)).split('\n')[0].matchAll(/\{ id: '([a-z]+)', label/g)].map((m) => m[1])
    const theirs = [...backend.match(new RegExp(`"${part}": \\(([^)]*)\\)`))[1].matchAll(/"([a-z]+)"/g)].map((m) => m[1])
    assert.ok(mine.length >= 3, `${part} has options`)
    assert.deepEqual(mine, theirs, `${part} equals the backend`)
    for (const id of mine) assert.ok(new RegExp(`\\b${id}: `).test(square), `${part}/${id} is in the square app table`)
  }
})

test('every starting look names a colour scheme, a font pair, shapes and feel that exist (W18-R46)', () => {
  const looks = read('../platform/src/themes/startingLooks.ts')
  const schemes = [...presets.slice(presets.indexOf('COLOUR_SCHEMES: {'), presets.indexOf('export const ALL_SCHEMES')).matchAll(/\{ id: '([a-z-]+)', name:/g)].map((m) => m[1])
  const pairs = [...presets.matchAll(/\{ id: '([a-z]+)', label: '[^']+', display:/g)].map((m) => m[1])
  const parts = (name) => {
    const block = presets.slice(presets.indexOf(`export const ${name}`), presets.indexOf('\nexport type', presets.indexOf(`export const ${name}`)))
    return Object.fromEntries([...block.matchAll(/\{ id: '([a-z]+)', options: \[(.*?)\] \}/g)].map((m) => [m[1], [...m[2].matchAll(/\{ id: '([a-z]+)'/g)].map((x) => x[1])]))
  }
  const shapes = parts('SHAPE_PARTS')
  const feels = parts('FEEL_PARTS')
  const entries = [...looks.matchAll(/\{ id: '([a-z-]+)', name: '([^']+)', hint: '([^']+)', scheme: '([a-z-]+)', fonts: '([a-z]+)',\s*shape: \{([^}]*)\}, feel: \{([^}]*)\}/g)]
  assert.equal(entries.length, 10)
  assert.equal(new Set(entries.map((m) => m[1])).size, 10, 'no id twice')
  assert.equal(new Set(entries.map((m) => m[2])).size, 10, 'no name twice')
  const pairsOf = (s) => [...s.matchAll(/([a-z]+): '([a-z]+)'/g)].map((m) => [m[1], m[2]])
  for (const [, id, , , scheme, fonts, shape, feel] of entries) {
    assert.ok(schemes.includes(scheme), `${id}: scheme ${scheme}`)
    assert.ok(pairs.includes(fonts), `${id}: fonts ${fonts}`)
    for (const [k, v] of pairsOf(shape)) assert.ok(shapes[k]?.includes(v), `${id}: shape ${k}=${v}`)
    for (const [k, v] of pairsOf(feel)) assert.ok(feels[k]?.includes(v), `${id}: feel ${k}=${v}`)
  }
})

test('the feel options equal the backend lists and the square app (W18-R44)', () => {
  const backend = read('../../backend/app/platform/theme_overrides.py')
  const square = read('../../square/frontend/src/themes/feel.ts')
  const from = presets.indexOf('export const FEEL_PARTS')
  const block = presets.slice(from, presets.indexOf('export type FeelLookChoice'))
  for (const part of ['mode', 'switch', 'density', 'text', 'motion', 'divider']) {
    const line = block.slice(block.indexOf(`id: '${part}'`)).split('\n')[0]
    const mine = [...line.matchAll(/\{ id: '([a-z]+)', label/g)].map((m) => m[1])
    const theirs = [...backend.match(new RegExp(`"${part}": \\(([^)]*)\\)`))[1].matchAll(/"([a-z]+)"/g)].map((m) => m[1])
    const sq = [...square.match(new RegExp(`  ${part}: \\[([^\\]]*)\\]`))[1].matchAll(/'([a-z]+)'/g)].map((m) => m[1])
    assert.ok(mine.length >= 2, `${part} has options`)
    assert.deepEqual(mine, theirs, `${part} equals the backend`)
    assert.deepEqual(mine, sq, `${part} equals the square app`)
  }
})

test('a season covers its days; a yearly one repeats and may cross the new year (W18-R49); the three rules are the same', () => {
  const once = { start: '2026-10-28', end: '2026-11-12', yearly: false }
  const day = (iso) => new Date(`${iso}T12:00:00Z`)
  assert.ok(seasonActive(once, day('2026-10-28')) && seasonActive(once, day('2026-11-12')))
  assert.ok(!seasonActive(once, day('2026-11-13')) && !seasonActive(once, day('2027-11-01')))
  const xmas = { start: '2026-12-20', end: '2027-01-05', yearly: true }
  assert.ok(seasonActive(xmas, day('2030-12-31')) && seasonActive(xmas, day('2031-01-05')) && !seasonActive(xmas, day('2031-01-06')))
  // the backend and the square server hold the same rule (their own tests run it on the same days)
  assert.match(read('../../backend/app/platform/theme_overrides.py'), /return a <= t <= b if a <= b else \(t >= a or t <= b\)/)
  assert.match(read('../../square/backend/app/tenancy.py'), /return a <= t <= b if a <= b else \(t >= a or t <= b\)/)
})

test('ten tinted colour sets of their own: names and colours differ from each other and from the theme schemes (W25-R62)', () => {
  const from = presets.indexOf('export const OWN_SCHEMES')
  const block = presets.slice(from, presets.indexOf('export const ALL_SCHEMES'))
  const sets = [...block.matchAll(/\{ id: '([a-z-]+)', name: '([^']+)', l: \['(#[0-9a-f]{6})', '(#[0-9a-f]{6})', '(#[0-9a-f]{6})'\], d: \['(#[0-9a-f]{6})', '(#[0-9a-f]{6})', '(#[0-9a-f]{6})'\] \}/g)].map((m) => ({ id: m[1], name: m[2], l: m.slice(3, 6).join('|'), d: m.slice(6, 9).join('|') }))
  assert.equal(sets.length, 10)
  assert.equal(new Set(sets.map((s) => s.id)).size, 10, 'no id twice')
  assert.equal(new Set(sets.map((s) => s.name)).size, 10, 'no name twice')
  assert.equal(new Set(sets.map((s) => s.l)).size, 10, 'no light colours twice')
  assert.equal(new Set(sets.map((s) => s.d)).size, 10, 'no dark colours twice')
  const themeIds = [...presets.slice(presets.indexOf('COLOUR_SCHEMES: {'), presets.indexOf('export const OWN_SCHEMES')).matchAll(/\{ id: '([a-z-]+)', name:/g)].map((m) => m[1])
  for (const { id } of sets) assert.ok(!themeIds.includes(id), `${id} is not also a theme scheme`)
})

test('the accent fonts of the picker equal the square app and the server, and the two Google font lists are the same file (W25-R63)', () => {
  const picker = read('../platform/src/themes/googleFonts.ts')
  const mine = [...picker.slice(picker.indexOf('export const ACCENT_CHOICES')).matchAll(/\{ id: '([a-z-]+)', label:/g)].map((m) => m[1])
  const square = read('../../square/frontend/src/themes/customFonts.ts')
  const block = square.slice(square.indexOf('export const ACCENTS'), square.indexOf('\n}\n', square.indexOf('export const ACCENTS')))
  const theirs = [...block.matchAll(/^  '?([a-z-]+)'?: \{/gm)].map((m) => m[1])
  assert.deepEqual(mine, [...theirs, 'headings'])
  const backend = read('../../backend/app/platform/theme_overrides.py')
  const ids = [...backend.match(/ACCENT_IDS: tuple\[str, \.\.\.\] = \(([^)]*)\)/)[1].matchAll(/"([a-z-]+)"/g)].map((m) => m[1])
  assert.deepEqual(mine, ids)
  assert.equal(read('../platform/src/themes/googleFonts.json'), read('../../backend/app/platform/google_fonts.json'))
})
