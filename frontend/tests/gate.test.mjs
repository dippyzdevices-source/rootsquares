// The site gate, browser side (W26-R20, ADR 099): the client asks the server `<base>/gate`, sends the passcode, and never lets the app start behind a closed gate;
// all three sites ask the gate before anything else. Run: npm run test:gate (from frontend/).
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { gateEnter, gateIsOpen, gateStatus } from '../ui/src/gate/gate.ts'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8')
const BASE = 'https://api.example.test/'
const calls = []

function serve(handler) {
  calls.length = 0
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), init })
    return handler(String(url), init)
  }
}
const json = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body })

test('the status is read from <base>/gate with the cookie', async () => {
  serve(() => json(200, { required: true, open: false }))
  assert.deepEqual(await gateStatus(BASE), { required: true, open: false, env: '' })
  assert.equal(calls[0].url, 'https://api.example.test/gate')
  assert.equal(calls[0].init.credentials, 'include')
})

test('the app may start with no gate, with a pass, or when the server cannot be asked; not behind a closed gate', async () => {
  serve(() => json(200, { required: false, open: true }))
  assert.equal(await gateIsOpen(BASE), true)
  serve(() => json(200, { required: true, open: true }))
  assert.equal(await gateIsOpen(BASE), true)
  serve(() => { throw new Error('down') })
  assert.equal(await gateIsOpen(BASE), true)
  serve(() => json(500, {}))
  assert.equal(await gateIsOpen(BASE), true)
  serve(() => json(200, { required: true, open: false }))
  assert.equal(await gateIsOpen(BASE), false)
})

test('the passcode goes in the body of a POST and the answers are told apart', async () => {
  serve(() => json(200, { required: true, open: true }))
  assert.equal(await gateEnter(BASE, 'pass phrase here 1234'), 'ok')
  assert.equal(calls[0].init.method, 'POST')
  assert.equal(calls[0].init.credentials, 'include')
  assert.deepEqual(JSON.parse(calls[0].init.body), { passcode: 'pass phrase here 1234' })
  serve(() => json(401, {}))
  assert.equal(await gateEnter(BASE, 'x'), 'wrong')
  serve(() => json(429, {}))
  assert.equal(await gateEnter(BASE, 'x'), 'limited')
  serve(() => json(503, {}))
  assert.equal(await gateEnter(BASE, 'x'), 'error')
  serve(() => { throw new Error('down') })
  assert.equal(await gateEnter(BASE, 'x'), 'error')
})

test('all three sites ask the gate before they start, and show the passcode screen when it is closed', () => {
  assert.match(read('platform/src/main.ts'), /gateStart\(apiBase\)[\s\S]*GateScreen[\s\S]*isSquareHost/)
  assert.match(read('admin/src/main.ts'), /gateStart\(apiBase\)[\s\S]*GateScreen[\s\S]*start\(\)/)
  const square = read('../square/frontend/src/main.ts')
  assert.match(square, /gateIsOpen\(\)[\s\S]*import\('\.\/boot'\)/)
  assert.doesNotMatch(square, /(?:from|import\()\s*['"][^'"]*squareConfig/) // the square's own configuration is behind the gate, so main.ts must not import it
})

test('the passcode is never stored by the browser code', () => {
  for (const file of ['ui/src/gate/gate.ts', 'ui/src/components/GateScreen.vue', '../square/frontend/src/gate/GateScreen.vue', '../square/frontend/src/services/gate.ts']) {
    assert.doesNotMatch(read(file), /localStorage|sessionStorage|document\.cookie/, file)
  }
})
