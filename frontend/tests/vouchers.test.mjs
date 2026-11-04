// Scoped voucher tests (run: npm run test:vouchers): the referral link is remembered, and the mock prices and vouchers behave like the platform (W14-R27).
import assert from 'node:assert/strict'
import { test } from 'node:test'

const store = new Map()
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) }, location: { search: '' } }
const { captureReferral, savedReferral } = await import('../platform/src/services/referral.ts')

test('a referral link keeps the code, upper case, and nothing else', () => {
  assert.equal(savedReferral(), '')
  captureReferral('?utm=x&ref=samaj15')
  assert.equal(savedReferral(), 'SAMAJ15')
  captureReferral('?ref=%3Cscript%3E') // not a code: ignored, the earlier one stays
  assert.equal(savedReferral(), 'SAMAJ15')
})

test('a saved code runs out after 30 days', () => {
  const real = Date.now
  Date.now = () => real() + 31 * 86_400_000
  try { assert.equal(savedReferral(), '') } finally { Date.now = real }
})
