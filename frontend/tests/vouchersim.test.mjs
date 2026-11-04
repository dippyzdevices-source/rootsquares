// The play checkout of the Vouchers page (run: npm run test:vouchersim) (W19-R35): it must do the arithmetic of backend/app/platform/vouchers.py.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { discountFor, simulate } from '../admin/src/features/voucherSim.ts'

const p = (code, value, stackable = true) => ({ code, kind: 'percent', value, stackable })
const f = (code, value, stackable = true) => ({ code, kind: 'fixed', value, stackable })

test('a percent is rounded to the nearest unit and a fixed amount never goes below zero', () => {
  assert.equal(discountFor(p('A', 20), 10_000), 2_000)
  assert.equal(discountFor(p('A', 33), 1_001), 330)
  assert.equal(discountFor(f('B', 5_000), 3_000), 3_000)
  assert.equal(discountFor(p('A', 20), 0), 0)
})

test('best: only the code that takes most off counts, a tie goes to the first typed', () => {
  const r = simulate(10_000, [p('A', 10, false), p('B', 30, false), p('C', 30, false)], 'best', 3)
  assert.deepEqual(r.used, [{ code: 'B', off: 3_000 }])
  assert.deepEqual(r.ignored.map((x) => x.code), ['A', 'C'])
  assert.equal(r.payable, 7_000)
})

test('sequential: 20 % then 10 % is 28 % off; additive: 30 % off', () => {
  assert.equal(simulate(10_000, [p('A', 20), p('B', 10)], 'sequential', 2).payable, 7_200)
  assert.equal(simulate(10_000, [p('A', 20), p('B', 10)], 'additive', 2).payable, 7_000)
})

test('codes over the limit and codes that cannot combine are left out; one code always counts', () => {
  const over = simulate(10_000, [p('A', 10), p('B', 10), p('C', 10)], 'additive', 2)
  assert.deepEqual(over.ignored, [{ code: 'C', why: 'extra' }])
  const blocked = simulate(10_000, [p('A', 10, false), p('B', 10)], 'additive', 2)
  assert.deepEqual(blocked.ignored, [{ code: 'A', why: 'notStackable' }])
  assert.equal(simulate(10_000, [p('A', 10, false)], 'additive', 2).payable, 9_000)
  assert.equal(simulate(10_000, [], 'best', 2).payable, 10_000)
})

test('what is left runs out: nothing more is taken off', () => {
  const r = simulate(1_000, [f('A', 1_000), f('B', 500)], 'additive', 2)
  assert.equal(r.payable, 0)
  assert.deepEqual(r.ignored, [{ code: 'B', why: 'nothingLeft' }])
})
