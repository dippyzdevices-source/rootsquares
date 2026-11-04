// Scoped tests (run: npm run test:region): the country fills in currency and phone country (W14-R31), and every audit action has words (W14-R31).
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { test } from 'node:test'
import { currencyFor, phoneCountryFor } from '../platform/src/services/countryDefaults.ts'

const platformSource = readFileSync(new URL('../platform/src/services/platformTypes.ts', import.meta.url), 'utf8')
// the codes inside `export const NAME = [ ... ]`
function list(name) {
  const start = platformSource.indexOf(`export const ${name}`)
  const open = platformSource.indexOf('[', start)
  const close = platformSource.indexOf(']', open)
  return [...platformSource.slice(open, close).matchAll(/'([A-Z]+)'/g)].map((m) => m[1])
}
const CURRENCIES = list('CURRENCIES')
const PHONE_COUNTRIES = list('PHONE_COUNTRIES')

test('a country suggests its currency and its phone rule, and an unknown one suggests nothing', () => {
  assert.ok(CURRENCIES.includes('NOK') && PHONE_COUNTRIES.includes('NO'))
  assert.equal(currencyFor('NO'), 'NOK')
  assert.equal(currencyFor('de'), 'EUR')
  assert.equal(currencyFor('GB'), 'GBP')
  assert.equal(phoneCountryFor('SE', PHONE_COUNTRIES), 'SE')
  assert.equal(phoneCountryFor('ES', PHONE_COUNTRIES), '') // no phone rule for it yet
  assert.equal(currencyFor('IN'), '') // INR is not offered
})

test('every suggestion is something the form offers', () => {
  for (const c of ['NO', 'SE', 'DK', 'IS', 'GB', 'US', 'FI', 'DE', 'IE', 'NL', 'FR', 'AT', 'ES', 'IT', 'PT', 'GR']) {
    const cur = currencyFor(c)
    assert.ok(cur === '' || CURRENCIES.includes(cur), `${c} -> ${cur}`)
  }
  for (const c of PHONE_COUNTRIES) assert.equal(phoneCountryFor(c, PHONE_COUNTRIES), c)
})

test('every audit action in the backend has a sentence in the Audit log words', () => {
  const en = JSON.parse(readFileSync(new URL('../admin/src/i18n/admin.en.json', import.meta.url), 'utf8'))
  const words = en.own.audit.events
  const root = new URL('../../backend/app/platform/', import.meta.url)
  const actions = new Set()
  for (const f of readdirSync(root).filter((n) => n.endsWith('.py'))) {
    const text = readFileSync(new URL(f, root), 'utf8')
    for (const m of text.matchAll(/_audit\(\s*"([a-z_]+\.[a-z_]+)"/g)) actions.add(m[1])
    for (const m of text.matchAll(/(?:action|REMINDER_ACTION)\s*=\s*"([a-z_]+\.[a-z_]+)"/g)) actions.add(m[1])
  }
  assert.ok(actions.size > 20)
  for (const a of actions) assert.ok(words[a.replace('.', '_')], `no words for the audit action ${a}`)
})
