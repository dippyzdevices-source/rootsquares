// The hierarchy of a custom package (run: npm run test:package) (W19-R25): what switching a part on or off brings along, and that every text the views use exists.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { buildGraph, stepOf, switchOff, switchOn } from '../admin/src/features/packageGraph.ts'

const n = (id, needs = [], core = false) => ({ id, name: id, desc: id, needs, core })
const g = buildGraph([n('login', [], true), n('admin', ['login'], true), n('settings', ['admin'], true), n('home', [], true), n('events', ['admin']), n('payments', ['admin']), n('tickets', ['events', 'payments', 'admin']), n('coupons', ['tickets', 'admin'])])

test('levels count the longest chain of needs and steps stop at five', () => {
  assert.deepEqual(['home', 'login', 'admin', 'events', 'tickets', 'coupons'].map((i) => g.info[i].lv), [0, 0, 1, 2, 3, 4])
  assert.equal(stepOf(g, 'coupons'), 4)
  assert.equal(g.ids[0], 'login')
})

test('a line is drawn only to a need that is not already needed through another need', () => {
  assert.deepEqual(g.info.tickets.direct.sort(), ['events', 'payments'])
  assert.deepEqual([...g.info.coupons.deep].sort(), ['admin', 'events', 'login', 'payments', 'tickets'])
})

test('switching on brings what it needs; switching off takes what needs it', () => {
  const on = new Set(['home'])
  assert.deepEqual(switchOn(g, on, 'tickets').sort(), ['admin', 'events', 'login', 'payments'])
  assert.ok(on.has('tickets') && on.has('login'))
  assert.deepEqual(switchOff(g, on, 'admin').sort(), ['events', 'payments', 'tickets'])
  assert.deepEqual([...on].sort(), ['admin'].slice(1).concat(['home', 'login']).sort())
})

test('the texts of the views exist', () => {
  const en = JSON.parse(readFileSync(new URL('../admin/src/i18n/admin.en.json', import.meta.url), 'utf8'))
  const pb = en.own.custom.pb
  for (const v of ['map', 'hierarchy', 'steps', 'outline']) assert.ok(pb.view[v] && pb.info[v].title && pb.info[v].text, v)
  for (const s of [0, 1, 2, 3, 4]) assert.ok(pb.step[s].name && pb.step[s].text, `step ${s}`)
})
