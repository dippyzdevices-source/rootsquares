// Scoped tests of the customer app's role model and route guard (run: npm run test:roles). Since W23-R82 there is one role (the square owner) and no console in this app.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ROLES, guardRedirect, isRole, landing } from '../platform/src/auth/roles.ts'

test('one role: the square owner (staff have their own application, ADR 083)', () => {
  assert.deepEqual([...ROLES], ['squareOwner'])
  assert.equal(isRole('squareOwner'), true)
  for (const r of ['squareAdmin', 'treasurer', 'volunteer', 'admin', '', null, undefined, 3]) assert.equal(isRole(r), false, String(r))
})

test('role-to-landing-route', () => {
  assert.equal(landing('squareOwner'), '/dashboard')
})

test('the landing is allowed by the guard for the role', () => {
  assert.equal(guardRedirect({ role: 'squareOwner', square: null }, landing('squareOwner')), null)
})

test('platform pages need a sign-in; public pages do not', () => {
  for (const p of ['/dashboard', '/squares/abc', '/squares/new', '/account']) assert.equal(guardRedirect({ role: null, square: null }, p), '/login', p)
  for (const p of ['/', '/pricing', '/login', '/signup', '/contact', '/case-study/bca']) assert.equal(guardRedirect({ role: null, square: null }, p), null, p)
})

test('a signed-in owner does not see the sign-in and sign-up pages again', () => {
  for (const p of ['/login', '/signup']) assert.equal(guardRedirect({ role: 'squareOwner', square: null }, p), '/dashboard', p)
})

test('a person without an organisation goes through onboarding first, and only they', () => {
  const noOrg = { role: 'squareOwner', square: null, needsOrg: true }
  for (const p of ['/dashboard', '/squares/abc', '/account']) assert.equal(guardRedirect(noOrg, p), '/organization/new', p)
  assert.equal(guardRedirect(noOrg, '/organization/new'), null)
  assert.equal(guardRedirect({ role: 'squareOwner', square: null }, '/organization/new'), '/dashboard') // already has one
  assert.equal(guardRedirect({ role: null, square: null }, '/organization/new'), '/login')
})

test('the customer app has no /admin console any more: the path is an ordinary public path to the guard', () => {
  assert.equal(guardRedirect({ role: null, square: null }, '/admin'), null)
  assert.equal(guardRedirect({ role: 'squareOwner', square: null }, '/admin/orders'), null)
})
