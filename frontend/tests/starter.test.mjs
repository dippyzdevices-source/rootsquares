// Scoped starter set tests (run: npm run test:starter): the kind of group decides what a new square starts with (W14-R10).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { MOCK_MODULES, MOCK_STARTER_SETS, allowedModules, arrangeModules, completeModules, modulesOfPackage, packageAdditions, recommendationGroups, recommendedModules, startingModules, withModule, withoutModule } from '../platform/src/services/modulesCatalogue.ts'

const set = (xs) => [...xs].sort()
const religious = MOCK_STARTER_SETS.find((s) => s.key === 'religious')
const cultural = MOCK_STARTER_SETS.find((s) => s.key === 'cultural')

test('cultural is the Recommended group, so a square without a kind starts the same way (W15-R27)', () => {
  // Grove starts with the whole cultural list; Square with the part of it that it includes
  assert.deepEqual(set(startingModules(MOCK_MODULES, 'grove', cultural)), set(recommendedModules(MOCK_MODULES)))
  assert.deepEqual(set(startingModules(MOCK_MODULES, 'square', cultural)), set(allowedModules(MOCK_MODULES, 'square').filter((k) => cultural.modules.includes(k))))
  assert.deepEqual(set(startingModules(MOCK_MODULES, 'square')), set(startingModules(MOCK_MODULES, 'square', cultural)))
})

test('a religious community starts with gatherings, people, donations and messages, and no ticket sales or paid memberships', () => {
  const start = startingModules(MOCK_MODULES, 'grove', religious)
  for (const on of ['events', 'members', 'payments', 'donations', 'messages']) assert.ok(start.includes(on), `${on} starts on`)
  for (const off of ['tickets', 'memberships', 'coupons', 'checkin']) assert.ok(!start.includes(off), `${off} starts off`)
  assert.deepEqual(set(completeModules(MOCK_MODULES, start)), set(start))
})

test('the package still limits what starts on: Roots has none, the Event pass keeps its own list', () => {
  assert.deepEqual(startingModules(MOCK_MODULES, 'roots', religious), [])
  assert.deepEqual(set(startingModules(MOCK_MODULES, 'event', religious)), set(allowedModules(MOCK_MODULES, 'event')))
  // Square does not include Donations (Grove): a religious Square starts without it
  const square = startingModules(MOCK_MODULES, 'square', religious)
  assert.ok(!square.includes('donations') && square.includes('messages'))
})

test('Check-in and Coupons are sub-switches of Tickets: on by default with it, each still switchable alone (W14-R13)', () => {
  const on = withModule(MOCK_MODULES, [], 'tickets')
  for (const k of ['events', 'payments', 'tickets', 'coupons', 'checkin']) assert.ok(on.includes(k), `${k} comes on with Tickets`)
  const noCoupons = withoutModule(MOCK_MODULES, on, 'coupons')
  assert.ok(noCoupons.includes('checkin') && noCoupons.includes('tickets') && !noCoupons.includes('coupons'))
  assert.ok(!withoutModule(MOCK_MODULES, on, 'tickets').includes('checkin'), 'turning Tickets off turns its sub-switches off')
  // a package that does not allow them (Square) does not get them
  assert.deepEqual(withModule(MOCK_MODULES, [], 'tickets', allowedModules(MOCK_MODULES, 'square')).filter((k) => ['coupons', 'checkin'].includes(k)), [])
  // a new Grove square of the cultural kind starts with them on
  assert.ok(startingModules(MOCK_MODULES, 'grove', cultural).includes('checkin'))
})

test('three views of the modules: the kind list is Recommended, the rest Good to have, and the package lists follow the packages (W15-R27)', () => {
  const keys = (xs) => xs.map((m) => m.key)
  const { recommended, goodToHave } = recommendationGroups(MOCK_MODULES, cultural.modules)
  assert.deepEqual(set(keys(recommended)), set(['events', 'tickets', 'coupons', 'checkin', 'payments', 'members', 'messages', 'gallery', 'committee', 'news', 'accounting']))
  assert.deepEqual(set(keys(goodToHave)), set(['memberships', 'donations', 'newsletter', 'volunteering', 'testimonials', 'sponsors', 'founders', 'magazines']))
  assert.equal(recommended.length + goodToHave.length, MOCK_MODULES.length)
  assert.ok(keys(recommended).indexOf('coupons') === keys(recommended).indexOf('tickets') + 1) // a sub-switch follows its parent
  assert.ok(keys(goodToHave).includes('memberships') && keys(goodToHave).includes('donations')) // their parents are Recommended, they stand alone here
  const religious_ = recommendationGroups(MOCK_MODULES, religious.modules)
  assert.ok(keys(religious_.recommended).includes('donations') && !keys(religious_.recommended).includes('tickets')) // each kind has its own list
  assert.equal(modulesOfPackage(MOCK_MODULES, 'roots').length, 0)
  assert.equal(modulesOfPackage(MOCK_MODULES, 'square').length, 9)
  assert.equal(modulesOfPackage(MOCK_MODULES, 'grove').length, MOCK_MODULES.length)
  assert.equal(keys(arrangeModules(MOCK_MODULES, ['members', 'memberships'])).join(), 'members,memberships')
})

test('a new square starts with the list of its kind, limited by the package (W15-R27)', () => {
  assert.deepEqual(set(startingModules(MOCK_MODULES, 'square', cultural)), set(['events', 'tickets', 'payments', 'members', 'messages', 'gallery', 'committee', 'accounting']))
  assert.ok(startingModules(MOCK_MODULES, 'grove', cultural).includes('coupons'))
  assert.ok(!startingModules(MOCK_MODULES, 'grove', cultural).includes('memberships'))
})

test('By package shows what each package adds: Root nothing, Square its 9, Grove the other 10, the Event pass its own list (W15-R30)', () => {
  const keys = (xs) => xs.map((m) => m.key)
  assert.equal(packageAdditions(MOCK_MODULES, 'roots').length, 0)
  assert.equal(packageAdditions(MOCK_MODULES, 'square').length, 9)
  const grove = keys(packageAdditions(MOCK_MODULES, 'grove'))
  assert.equal(grove.length, 10)
  assert.deepEqual(set(grove), set(['news', 'magazines', 'donations', 'newsletter', 'coupons', 'checkin', 'volunteering', 'testimonials', 'sponsors', 'founders']))
  assert.deepEqual(set([...keys(packageAdditions(MOCK_MODULES, 'square')), ...grove]), set(keys(MOCK_MODULES))) // Square + Grove's additions = everything, nothing twice
  assert.equal(packageAdditions(MOCK_MODULES, 'event').length, modulesOfPackage(MOCK_MODULES, 'event').length)
})
