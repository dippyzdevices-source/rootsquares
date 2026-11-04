// Billing and payments, platform frontend (run: npm run test:billing) (W12-R22): the prices shown, the words every payment state needs, and the start flow.
// The backend side of the same rules is backend/tests/billing (guide 14); test_17_consistency.py there also compares these prices with the database defaults.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { EVENT_PASS_DAYS, LAUNCH_PACKAGES, RUNNING_PLANS, usd } from '@rootsquares/ui/mock/pricing'
import { startQuery, startTarget } from '../platform/src/features/platform/startFlow.ts'

const en = { ...JSON.parse(readFileSync(new URL('../ui/src/i18n/en.json', import.meta.url), 'utf8')), ...JSON.parse(readFileSync(new URL('../platform/src/i18n/en.json', import.meta.url), 'utf8')) } // the shared messages and the customer's own
const admin = JSON.parse(readFileSync(new URL('../admin/src/i18n/admin.en.json', import.meta.url), 'utf8')) // the console's own wording (ADR 083)
const at = (path) => [en, admin].map((m) => path.split('.').reduce((o, k) => (o == null ? undefined : o[k]), m)).find((v) => v !== undefined)
const source = (rel) => readFileSync(new URL(`../platform/src/${rel}`, import.meta.url), 'utf8')

test('no price is written in the frontend code: the plans are a list of ids, the amounts come from the platform (W14-R29)', () => {
  assert.deepEqual(LAUNCH_PACKAGES.map((p) => p.id), ['roots', 'square', 'grove'])
  assert.deepEqual(RUNNING_PLANS.map((p) => p.id), ['keep', 'live', 'event'])
  for (const p of [...LAUNCH_PACKAGES, ...RUNNING_PLANS]) assert.deepEqual(Object.keys(p).filter((k) => /minor/i.test(k)), [], `${p.id} holds an amount`)
  assert.doesNotMatch(source('../../ui/src/mock/pricing.ts'), /[Mm]inor:\s*[\d_]+/)
  for (const file of ['features/marketing/PricingView.vue', 'features/marketing/LandingView.vue', 'features/platform/CreateSquareView.vue']) {
    assert.doesNotMatch(source(file), /\b(?:monthlyMinor|yearlyMinor)\b|\.minor\b/, `${file} reads an amount from the code`)
  }
  assert.equal(EVENT_PASS_DAYS, 45)
})

test('the Pricing page says the prices include tax where it applies', () => {
  assert.match(at('marketing.pricing.taxLine'), /include tax/)
  assert.match(source('features/marketing/PricingView.vue'), /pricing-tax/)
})

test('money is shown in whole dollars, with cents only when there are cents', () => {
  assert.equal(usd(14900), '$149')
  assert.equal(usd(2500), '$25')
  assert.equal(usd(1875), '$18.75')
  assert.equal(usd(0), '$0')
})

test('every kind of order has a name in the payment history', () => {
  for (const k of ['upgrade', 'running', 'first', 'eventPass', 'eventUpgrade']) assert.ok(at(`portal.checkout.${k}`), `portal.checkout.${k}`)
  for (const s of ['pending', 'paid', 'cancelled', 'failed', 'refunded']) assert.ok(at(`portal.checkout.states.${s}`), `portal.checkout.states.${s}`)
})

test('every state of the owner console Subscriptions page has a label', () => {
  for (const s of ['trial', 'unpaid', 'renewing', 'ending', 'failed', 'asleep', 'paid', 'expired']) assert.ok(at(`own.subState.${s}`), `own.subState.${s}`)
})

test('the Billing page boxes have all their words', () => {
  const need = [
    'portal.first.title', 'portal.first.body', 'portal.first.endedTitle', 'portal.first.endedBody', 'portal.first.package', 'portal.first.payMonth', 'portal.first.payYear',
    'portal.renewal.title', 'portal.renewal.body', 'portal.renewal.endingTitle', 'portal.renewal.endingBody', 'portal.renewal.cancel', 'portal.renewal.resume', 'portal.renewal.cancelled', 'portal.renewal.resumed',
    'portal.failed.title', 'portal.failed.body', 'portal.failed.update',
    'portal.eventPass.payTitle', 'portal.eventPass.payBody', 'portal.eventPass.payButton',
    'portal.payments.methodReady', 'portal.payments.methodButton',
    'own.square.payments', 'own.square.refund', 'own.square.refunded', 'own.square.refundTitle', 'own.square.refundText', 'own.square.refundNote',
    'plat.create.billingCountry', 'plat.create.billingCountryHint', 'plat.create.choose',
  ]
  for (const key of need) assert.ok(at(key), key)
})

test('the pay buttons and the landing line show amounts, never a fixed currency', () => {
  assert.match(at('portal.first.payMonth'), /\{amount\}/)
  assert.match(at('portal.first.payYear'), /\{amount\}/)
  assert.match(at('landing.hero.price'), /\{launch\}.*\{month\}/)
  assert.doesNotMatch(at('landing.hero.price'), /\bkr\b/)
})

test('the start flow keeps only what a visitor chose and sends the signed-in to Create square', () => {
  assert.deepEqual(startQuery({ package: 'roots', theme: 'japandi-atelier', junk: 'x', running: ['a', 'b'] }), { package: 'roots', theme: 'japandi-atelier' })
  assert.deepEqual(startQuery({}), {})
  assert.deepEqual(startTarget(true, { package: 'grove' }), { path: '/squares/new', query: { package: 'grove' } })
  assert.deepEqual(startTarget(false, { running: 'event' }), { path: '/signup', query: { running: 'event' } })
})

test('Pricing and Templates lead to the real flow, not the prototype wizard', () => {
  for (const file of ['features/marketing/PricingView.vue', 'features/marketing/TemplatesView.vue']) {
    const text = source(file)
    assert.doesNotMatch(text, /path:\s*'\/start'/, `${file} still points at /start`)
    assert.match(text, /startTarget/, `${file} should use startTarget`)
  }
})

test('Create square has no preselected country or currency', () => {
  const text = source('features/platform/CreateSquareView.vue')
  assert.match(text, /const currency = ref<string>\(''\)/)
  assert.match(text, /const phoneCountry = ref<string>\(''\)/)
})
