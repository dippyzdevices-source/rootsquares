// Separation of the two applications and the shared package (ADR 083, 084; run: npm run test:separation). A static walk of the import graph from each entry:
// the customer app (src/) must not reach any admin code, wording or API address; the admin application (admin/src) may reach only its own files and @rootsquares/ui;
// the ui package may import no application; and the package manifests keep the same boundary (no identity provider in admin, no app in ui).
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

const FE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const CUST_SRC = path.join(FE, 'platform/src')
const ADMIN_SRC = path.join(FE, 'admin/src')
const UI_SRC = path.join(FE, 'ui/src')
const EXT = ['', '.ts', '.vue', '.json', '.css', '/index.ts']

/** `alias` is what "@/" means in the application whose files are being read (each application has its own src). */
function resolve(from, spec, alias) {
  let base
  if (spec.startsWith('@/')) base = path.join(alias, spec.slice(2))
  else if (spec.startsWith('@rootsquares/ui/')) base = path.join(UI_SRC, spec.slice('@rootsquares/ui/'.length)) // the shared package
  else if (spec.startsWith('.')) base = path.resolve(path.dirname(from), spec)
  else return null // a package
  for (const e of EXT) {
    const p = path.normalize(base + e)
    if (fs.existsSync(p) && fs.statSync(p).isFile()) return p
  }
  return null
}

/** Every file reachable from an entry through static and dynamic imports (CSS @import is ignored: styles are shared by design). */
function graph(entry, alias) {
  const seen = new Set()
  const todo = [entry]
  while (todo.length) {
    const file = todo.pop()
    if (seen.has(file)) continue
    seen.add(file)
    if (!/\.(ts|vue)$/.test(file)) continue
    const text = fs.readFileSync(file, 'utf8')
    for (const m of text.matchAll(/(?:from|import)\s*\(?\s*['"]([^'"]+)['"]/g)) {
      const r = resolve(file, m[1], alias)
      if (r) todo.push(r)
    }
  }
  return seen
}

const customer = [...graph(path.join(CUST_SRC, 'main.ts'), CUST_SRC)]
const admin = [...graph(path.join(ADMIN_SRC, 'main.ts'), ADMIN_SRC)]
const inside = (f, dir) => f.startsWith(dir + path.sep)
const rel = (f) => path.relative(FE, f).replaceAll('\\', '/')
const code = (files) => files.filter((x) => /\.(ts|vue)$/.test(x))
const read = (f) => fs.readFileSync(f, 'utf8')
const manifest = (pkg) => JSON.parse(read(path.join(FE, pkg, 'package.json')))
const depNames = (m) => Object.keys({ ...m.dependencies, ...m.devDependencies, ...m.peerDependencies })

test('the walk finds both applications', () => {
  assert.ok(customer.length > 150, `customer graph: ${customer.length} files`)
  assert.ok(admin.length > 40, `admin graph: ${admin.length} files`)
  assert.ok(customer.map(rel).includes('platform/src/features/marketing/routes.ts'))
  assert.ok(admin.map(rel).includes('admin/src/features/OwnerOverviewView.vue'))
})

test('the customer app reaches no admin code', () => {
  assert.deepEqual(customer.filter((f) => inside(f, path.join(FE, 'admin'))).map(rel), [])
})

test('the customer app holds no admin API address, route or wording', () => {
  const hits = []
  for (const f of code(customer)) {
    const t = read(f)
    if (/\/api\/admin/.test(t)) hits.push(`${rel(f)}: /api/admin`)
    if (/['"`]\/owner(['"`/])/.test(t)) hits.push(`${rel(f)}: a /owner route`)
    if (/['"`]own\.[a-z]/.test(t)) hits.push(`${rel(f)}: an own.* text key`)
    if (/['"`]adm\.[a-z]/.test(t)) hits.push(`${rel(f)}: an adm.* text key`)
    if (/is_platform_admin/.test(t)) hits.push(`${rel(f)}: is_platform_admin`)
  }
  assert.deepEqual(hits, [])
})

test('the customer message files hold no admin wording', () => {
  for (const f of ['en.json', 'no.json']) {
    const json = JSON.parse(read(path.join(UI_SRC, 'i18n', f)))
    assert.equal(json.own, undefined, `${f}: own`)
    assert.equal(json.adm, undefined, `${f}: adm`)
    assert.deepEqual(Object.keys(json.pages ?? {}).filter((k) => k.startsWith('owner')), [], `${f}: pages.owner*`)
  }
})

test('the admin application reaches only its own files and the ui package', () => {
  const bad = admin.filter((f) => !inside(f, ADMIN_SRC) && !inside(f, UI_SRC))
  assert.deepEqual(bad.map(rel), [])
})

test('the admin application talks to the staff API only', () => {
  const hits = []
  for (const f of code(admin)) {
    const t = read(f)
    if (/\/api\/platform/.test(t)) hits.push(`${rel(f)}: /api/platform`)
    if (/VITE_API_BASE_URL/.test(t)) hits.push(`${rel(f)}: VITE_API_BASE_URL`)
  }
  assert.deepEqual(hits, [])
})

test('the ui package imports no application', () => {
  const hits = []
  const walk = (dir) => fs.readdirSync(dir).flatMap((n) => (fs.statSync(path.join(dir, n)).isDirectory() ? walk(path.join(dir, n)) : [path.join(dir, n)]))
  for (const f of code(walk(UI_SRC))) {
    for (const m of read(f).matchAll(/(?:from|import)\s*\(?\s*['"]([^'"]+)['"]/g)) {
      const spec = m[1]
      if (spec.startsWith('@/')) hits.push(`${rel(f)}: ${spec}`)
      else if (spec.startsWith('.')) {
        const target = path.resolve(path.dirname(f), spec)
        if (!inside(target, UI_SRC) && target !== UI_SRC) hits.push(`${rel(f)}: ${spec} leaves the package`)
      }
    }
  }
  assert.deepEqual(hits, [])
})

test('the package manifests keep the boundary: no identity provider in admin, no app in ui, the apps never name each other', () => {
  const forbidden = /^@(supabase|neondatabase)\//
  assert.deepEqual(depNames(manifest('admin')).filter((d) => forbidden.test(d)), [])
  assert.deepEqual(depNames(manifest('ui')).filter((d) => /^@rootsquares\/(admin|platform)$/.test(d)), [])
  assert.deepEqual(depNames(manifest('admin')).filter((d) => d === '@rootsquares/platform'), [])
  assert.deepEqual(depNames(manifest('platform')).filter((d) => d === '@rootsquares/admin'), [])
})

test('the shared message files (ui) hold only wording the admin application or the ui package references; the rest is the customer app\'s own (ADR 084 stage 6)', () => {
  const walk = (dir) => fs.readdirSync(dir).flatMap((n) => (fs.statSync(path.join(dir, n)).isDirectory() ? walk(path.join(dir, n)) : [path.join(dir, n)]))
  const used = [...code(walk(ADMIN_SRC)), ...code(walk(UI_SRC))].map(read).join('\n')
  // a key written as 'ns.something', a key built as ns.something${...}, or the bare name in quotes (a dynamic lookup)
  const referenced = (ns) => new RegExp(String.raw`['"` + '`' + String.raw`]${ns}\.|\b${ns}\.[a-zA-Z]+\$\{|['"` + '`' + String.raw`]${ns}['"` + '`' + String.raw`]`).test(used)
  for (const lang of ['en', 'no']) {
    const shared = JSON.parse(read(path.join(UI_SRC, 'i18n', `${lang}.json`)))
    const customerOwn = JSON.parse(read(path.join(CUST_SRC, 'i18n', `${lang}.json`)))
    assert.deepEqual(Object.keys(shared).filter((ns) => !referenced(ns)), [], `${lang}: shared namespaces nobody in admin or ui uses (move them to platform/src/i18n)`)
    assert.deepEqual(Object.keys(customerOwn).filter((ns) => referenced(ns)), [], `${lang}: customer namespaces that admin or ui use (move them to ui/src/i18n)`)
    assert.deepEqual(Object.keys(shared).filter((ns) => ns in customerOwn), [], `${lang}: a namespace in both files`)
  }
})
