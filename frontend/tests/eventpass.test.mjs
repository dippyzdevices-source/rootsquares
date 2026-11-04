// Scoped Event pass tests (run: npm run test:eventpass): the modules of the pass and the Members/Memberships rule (W11, ADR 044).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { MOCK_MODULES, allowedModules, completeModules, startingModules, withoutModule } from '../platform/src/services/modulesCatalogue.ts'

const set = (xs) => [...xs].sort()

test('the Event pass has what a single event needs, nothing else', () => {
  const allowed = allowedModules(MOCK_MODULES, 'event')
  assert.deepEqual(set(allowed), set(['events', 'payments', 'tickets', 'coupons', 'checkin', 'members', 'volunteering', 'accounting', 'sponsors', 'messages']))
  for (const out of ['gallery', 'news', 'magazines', 'newsletter', 'testimonials', 'committee', 'founders', 'memberships']) assert.ok(!allowed.includes(out), `${out} is not in the pass`)
})

test('a pass starts with all of its modules, and every one of them is closed under what it needs', () => {
  const start = startingModules(MOCK_MODULES, 'event')
  assert.deepEqual(set(start), set(allowedModules(MOCK_MODULES, 'event')))
  assert.deepEqual(set(completeModules(MOCK_MODULES, start)), set(start))
})

test('Members works alone; Memberships brings Members and Payments; Volunteering brings Members, not Memberships', () => {
  assert.deepEqual(set(completeModules(MOCK_MODULES, ['members'])), ['members'])
  assert.deepEqual(set(completeModules(MOCK_MODULES, ['memberships'])), set(['memberships', 'members', 'payments']))
  assert.deepEqual(set(completeModules(MOCK_MODULES, ['volunteering'])), set(['volunteering', 'events', 'members']))
})

test('switching Members off switches Memberships and Volunteering off, but switching Memberships off keeps Members', () => {
  const all = ['events', 'payments', 'members', 'memberships', 'volunteering']
  assert.deepEqual(set(withoutModule(MOCK_MODULES, all, 'members')), ['events', 'payments'])
  assert.deepEqual(set(withoutModule(MOCK_MODULES, all, 'memberships')), set(['events', 'payments', 'members', 'volunteering']))
})
