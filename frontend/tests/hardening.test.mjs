// Hardening of the three frontend packages (ADR 084 section 3; run: npm run test:hardening). Source and configuration checks, no build needed:
// banned patterns in the admin application, which environment names each app may read, the admin host's headers, exact dependency versions, install hygiene.
// The checks of the built output are in built.test.mjs (they need `npm run build` and `npm run build:admin` first).
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

const FE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (...p) => fs.readFileSync(path.join(FE, ...p), 'utf8')
const rel = (f) => path.relative(FE, f).replaceAll('\\', '/')
const walk = (dir) => fs.readdirSync(dir).flatMap((n) => (['node_modules', 'dist'].includes(n) ? [] : fs.statSync(path.join(dir, n)).isDirectory() ? walk(path.join(dir, n)) : [path.join(dir, n)]))
const sources = (pkg) => walk(path.join(FE, pkg, 'src')).filter((f) => /\.(ts|vue)$/.test(f))

// v-html writes markup into the page. Two admin files may, because the markup is drawn by our own code from numbers (the QR code of the authenticator set-up, the lines of the
// package map); no text that came from the server goes through it. Any other use fails this test and has to be argued for here.
const V_HTML_ALLOWED = ['admin/src/views/AdminEnrolView.vue', 'admin/src/features/PackageBuilder.vue']

test('the admin application uses no eval, no dynamic Function, no raw HTML writes', () => {
  const hits = []
  for (const f of [...sources('admin'), ...sources('ui')]) {
    const t = read(rel(f))
    if (/\beval\s*\(/.test(t)) hits.push(`${rel(f)}: eval`)
    if (/\bnew\s+Function\s*\(/.test(t)) hits.push(`${rel(f)}: new Function`)
    if (/\.(innerHTML|outerHTML)\s*=|insertAdjacentHTML\s*\(|document\.write\s*\(/.test(t)) hits.push(`${rel(f)}: a raw HTML write`)
    if (/\bv-html\s*=/.test(t) && !V_HTML_ALLOWED.includes(rel(f))) hits.push(`${rel(f)}: v-html`)
  }
  assert.deepEqual(hits, [])
})

test('v-html is used only where the list above says, and only with markup the code draws itself', () => {
  const users = sources('admin').filter((f) => /\bv-html\s*=/.test(read(rel(f)))).map(rel).sort()
  assert.deepEqual(users, [...V_HTML_ALLOWED].sort())
})

test('the admin application stores nothing in the browser, and no package writes a token, secret or password there', () => {
  const adminUse = sources('admin').filter((f) => /\b(localStorage|sessionStorage|indexedDB|document\.cookie)\b/.test(read(rel(f)))).map(rel)
  assert.deepEqual(adminUse, [], 'the staff session is an HttpOnly cookie set by the server; the application keeps nothing')
  const hits = []
  for (const f of [...sources('platform'), ...sources('ui')]) {
    for (const m of read(rel(f)).matchAll(/(?:local|session)Storage\.setItem\(\s*([^,)]+)/g)) if (/token|secret|password|passwd|jwt/i.test(m[1])) hits.push(`${rel(f)}: ${m[1].trim()}`)
  }
  assert.deepEqual(hits, [])
})

test('the admin application loads no script or style from another origin', () => {
  const hits = []
  const html = read('admin', 'index.html')
  if (/<(script|link)[^>]+(src|href)=["']https?:/i.test(html)) hits.push('admin/index.html: an external script or link')
  for (const f of [...sources('admin'), ...walk(path.join(FE, 'admin/src')).filter((x) => x.endsWith('.css')), ...walk(path.join(FE, 'ui/src')).filter((x) => x.endsWith('.css'))]) {
    const t = read(rel(f))
    if (/@import\s+(url\()?["']?https?:/i.test(t)) hits.push(`${rel(f)}: an external @import`)
    if (/<(script|link)[^>]+(src|href)=["']https?:/i.test(t)) hits.push(`${rel(f)}: an external script or link`)
  }
  assert.deepEqual(hits, [])
})

// A VITE_ value is public by design (it is written into the bundle). So a name that says it is a secret may not exist, and each app reads only the names listed for it.
const viteNames = (pkg) => [...new Set(sources(pkg).flatMap((f) => [...read(rel(f)).matchAll(/import\.meta\.env\.(VITE_[A-Z0-9_]+)/g)].map((m) => m[1])))].sort()

test('no environment name that is read by a frontend says secret, token, password or private key', () => {
  const bad = ['platform', 'admin', 'ui'].flatMap((p) => viteNames(p).filter((n) => /(SECRET|TOKEN|PASSWORD|PRIVATE)/.test(n) || (/KEY/.test(n) && !/PUBLIC/.test(n))).map((n) => `${p}: ${n}`))
  assert.deepEqual(bad, [])
})

test('the admin application reads one environment name, the API origin, and the ui package none', () => {
  assert.deepEqual(viteNames('admin'), ['VITE_ADMIN_API_BASE_URL'])
  assert.deepEqual(viteNames('ui'), [])
})

test('the admin host: no source maps, strict headers, nothing indexed', () => {
  assert.match(read('admin', 'vite.config.ts'), /sourcemap:\s*false/)
  const headers = read('admin', 'public', '_headers')
  for (const need of ['X-Frame-Options: DENY', 'X-Content-Type-Options: nosniff', 'Referrer-Policy: no-referrer', 'X-Robots-Tag: noindex', 'Cache-Control: no-store', "default-src 'self'", "script-src 'self'", "frame-ancestors 'none'", "base-uri 'self'"]) {
    assert.ok(headers.includes(need), `admin/public/_headers lacks: ${need}`)
  }
  assert.doesNotMatch(headers, /script-src[^;]*'unsafe-(inline|eval)'/)
  assert.match(read('admin', 'public', 'robots.txt'), /Disallow:\s*\//)
  assert.match(read('admin', 'index.html'), /noindex/)
})

test('every dependency of the three packages is an exact version', () => {
  const bad = []
  for (const p of ['platform', 'admin', 'ui']) {
    const m = JSON.parse(read(p, 'package.json'))
    for (const group of ['dependencies', 'devDependencies']) {
      for (const [name, range] of Object.entries(m[group] ?? {})) {
        if (name === '@rootsquares/ui' && range === '*') continue // the workspace package itself
        if (!/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/.test(range)) bad.push(`${p}: ${name}@${range}`)
      }
    }
  }
  assert.deepEqual(bad, [])
})

test('installs run no package scripts and write exact versions', () => {
  const npmrc = read('.npmrc')
  assert.match(npmrc, /^ignore-scripts=true$/m)
  assert.match(npmrc, /^save-exact=true$/m)
})
