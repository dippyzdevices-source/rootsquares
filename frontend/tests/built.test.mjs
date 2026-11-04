// The built output of the two applications (ADR 084 section 3.3; run: npm run test:built AFTER `npm run build` and `npm run build:admin`).
// The source checks (separation.test.mjs, hardening.test.mjs) say what the code may import; this says what actually shipped: the customer bundle holds no staff API address or
// staff wording, the admin bundle holds no customer API address, identity-provider code or source map, and the admin host's files are in place.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

const FE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const PLATFORM = path.join(FE, 'platform/dist')
const ADMIN = path.join(FE, 'admin/dist')
const walk = (dir) => fs.readdirSync(dir).flatMap((n) => (fs.statSync(path.join(dir, n)).isDirectory() ? walk(path.join(dir, n)) : [path.join(dir, n)]))
const text = (dir, re) => walk(dir).filter((f) => re.test(f)).map((f) => [path.relative(dir, f).replaceAll('\\', '/'), fs.readFileSync(f, 'utf8')])

for (const [name, dir, cmd] of [['customer', PLATFORM, 'npm run build'], ['admin', ADMIN, 'npm run build:admin']]) {
  test(`the ${name} build exists`, () => {
    assert.ok(fs.existsSync(path.join(dir, 'index.html')), `${path.relative(FE, dir)}/index.html is missing: run ${cmd} first`)
  })
}

test('the customer bundle holds no staff API address and no staff wording', () => {
  const hits = []
  for (const [f, t] of text(PLATFORM, /\.(js|html|css)$/)) {
    if (/\/api\/admin/.test(t)) hits.push(`${f}: /api/admin`)
    if (/rootsquares-admin/.test(t)) hits.push(`${f}: the staff request header`)
    if (/rs_admin/.test(t)) hits.push(`${f}: the staff cookie name`)
    if (/["']adm\.name["']|adm:\{name:/.test(t)) hits.push(`${f}: the admin wording`)
  }
  assert.deepEqual(hits, [])
})

test('the admin bundle holds no customer API address and no identity-provider code', () => {
  const hits = []
  for (const [f, t] of text(ADMIN, /\.(js|html|css)$/)) {
    if (/\/api\/platform/.test(t)) hits.push(`${f}: /api/platform`)
    if (/VITE_API_BASE_URL|VITE_AUTH_/.test(t)) hits.push(`${f}: a customer environment name`)
    if (/supabase|neondatabase|better-auth|@daveyplate/i.test(t)) hits.push(`${f}: identity-provider code`)
  }
  assert.deepEqual(hits, [])
})

test('the admin build publishes no source map and points to none', () => {
  assert.deepEqual(walk(ADMIN).filter((f) => f.endsWith('.map')).map((f) => path.relative(ADMIN, f)), [])
  const hits = text(ADMIN, /\.(js|css)$/).filter(([, t]) => /sourceMappingURL=/.test(t)).map(([f]) => f)
  assert.deepEqual(hits, [])
})

test('the admin build loads only its own files and carries the host files', () => {
  const html = fs.readFileSync(path.join(ADMIN, 'index.html'), 'utf8')
  assert.doesNotMatch(html, /<(script|link)[^>]+(src|href)=["']https?:/i)
  assert.match(html, /noindex/)
  for (const f of ['_headers', 'robots.txt']) assert.ok(fs.existsSync(path.join(ADMIN, f)), `admin/dist/${f} is missing`)
})
