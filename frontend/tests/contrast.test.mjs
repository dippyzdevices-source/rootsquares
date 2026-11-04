// WCAG AA check of the Brass token pairs (light and dark), read from the CSS the app ships (ui/src/styles/brass.css).
// Run only this test: npm run test:contrast
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const css = readFileSync(new URL('../ui/src/styles/brass.css', import.meta.url), 'utf8')

function block(selector) {
  const start = css.indexOf(selector + '{')
  assert.ok(start >= 0, `block ${selector} not found`)
  return css.slice(start, css.indexOf('}', start))
}
const vars = (b) => Object.fromEntries([...b.matchAll(/--color-([\w-]+):(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2].toLowerCase()]))
const light = vars(block('[data-brand="brass"]'))
const dark = { ...light, ...vars(block('[data-brand="brass"][data-theme="dark"]')) }

const lum = (h) => {
  const n = parseInt(h.slice(1), 16)
  return [n >> 16, (n >> 8) & 255, n & 255]
    .map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) })
    .reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0)
}
const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05) }

// [foreground, background, minimum]: text >= 4.5, large text and UI >= 3 (same pairs as Brass Foundations.html)
const TEXT = [
  ['text', 'bg'], ['text', 'surface'], ['text-muted', 'bg'], ['text-muted', 'surface'], ['text-muted', 'surface-sunken'],
  ['brass-text', 'bg'], ['brass-text', 'surface'], ['brass-text', 'surface-sunken'], ['brass-text', 'brass-subtle'],
  ['on-accent', 'accent'], ['success', 'bg'], ['success', 'success-subtle'], ['warning', 'warning-subtle'],
  ['danger', 'danger-subtle'], ['info', 'info-subtle'],
].map(([f, b]) => [f, b, 4.5])
const UI = [['brass', 'bg', 3], ['border-strong', 'surface', 3]]

for (const [name, t] of [['light', light], ['dark', dark]]) {
  for (const [f, b, min] of [...TEXT, ...UI]) {
    test(`${name}: ${f} on ${b} >= ${min}`, () => {
      assert.ok(t[f] && t[b], `missing token ${f} or ${b}`)
      const r = ratio(t[f], t[b])
      assert.ok(r >= min, `${t[f]} on ${t[b]} = ${r.toFixed(2)}, needs ${min}`)
    })
  }
}
