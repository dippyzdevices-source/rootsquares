// How the two applications tell apart in a browser (W26-R23): each has its own favicon (the admin one carries the plum dot), the admin tab title starts with the word
// Admin, and the customer app has a title per page. Run: npm run test:identity (from frontend/).
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8')

test('both applications link their own SVG favicon, and the files are the mark with and without the dot', () => {
  for (const app of ['platform', 'admin']) {
    assert.match(read(`${app}/index.html`), /<link rel="icon" type="image\/svg\+xml" href="\/favicon\.svg"/, app)
    const svg = read(`${app}/public/favicon.svg`)
    assert.match(svg, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 24 24">/, app)
    assert.match(svg, /prefers-color-scheme: dark/, `${app}: a dark browser gets its own colours`)
    assert.match(svg, /<rect class="o"/, app)
  }
  // an SVG is XML: two hyphens inside a comment make the whole file invalid and the browser silently shows no icon (this happened once, W26-R23)
  for (const app of ['platform', 'admin']) {
    for (const comment of read(`${app}/public/favicon.svg`).matchAll(/<!--([\s\S]*?)-->/g)) assert.ok(!comment[1].includes('--'), `${app}: a comment holds two hyphens`)
  }
  assert.doesNotMatch(read('platform/public/favicon.svg'), /<circle/) // the customer mark has no dot
  const admin = read('admin/public/favicon.svg')
  assert.match(admin, /<circle class="d"/) // the admin mark has the dot
  assert.match(admin, /#6b3f69/i) // in the admin colour (--color-admin, light)
  assert.match(admin, /#c79bc4/i) // and its dark side
})

test('the admin tab title starts with Admin, and the customer app sets a title per page', () => {
  assert.match(read('admin/index.html'), /<title>Admin · rootsquares<\/title>/)
  assert.match(read('admin/src/main.ts'), /document\.title = key \? `\$\{tag\} · \$\{t\(key\)\} · \$\{t\('app\.name'\)\}`/)
  const customer = read('platform/src/main.ts')
  assert.match(customer, /router\.afterEach/)
  assert.match(customer, /document\.title = key \?/)
})

test('the admin colour is a role in scheme.css and the header uses it, not a hex value', () => {
  const scheme = read('ui/src/styles/scheme.css')
  assert.match(scheme, /--color-admin: #6b3f69/)
  assert.match(scheme, /--color-admin: #c79bc4/)
  const css = read('ui/src/styles/ext-app.css')
  assert.match(css, /\.pt--admin \.pt-top\{border-top:4px solid var\(--color-admin\)/)
  assert.match(css, /\.pt-pill\{[^}]*var\(--color-admin\)/)
})

test('both applications show the environment strip; the word comes from the server (display only)', () => {
  for (const file of ['platform/src/App.vue', 'admin/src/AdminApp.vue']) {
    const app = read(file)
    assert.match(app, /import EnvBanner from '@rootsquares\/ui\/components\/EnvBanner\.vue'/, file)
    assert.match(app, /<EnvBanner :label="envLabel" \/>\s*<RouterView \/>/, file) // above every page
  }
  for (const file of ['platform/src/main.ts', 'admin/src/main.ts']) assert.match(read(file), /setEnvLabel\(\w+\.env\)/, file) // stored before anything is mounted
  assert.match(read('ui/src/components/GateScreen.vue'), /<EnvBanner :label="envLabel" \/>/) // the passcode screen shows it too
  const banner = read('ui/src/components/EnvBanner.vue')
  assert.match(banner, /v-if="name"/) // no label, no strip
  assert.match(banner, /role="status"/)
  assert.doesNotMatch(banner, /import\.meta\.env/) // the label is handed in: the component reads no environment itself
  const css = read('ui/src/styles/ext-app.css')
  assert.match(css, /\.env-bar--staging\{[^}]*var\(--color-warning-subtle\)[^}]*var\(--color-warning\)/)
  assert.match(css, /\.env-bar--local\{[^}]*var\(--color-info-subtle\)[^}]*var\(--color-info\)/)
  const messages = JSON.parse(read('ui/src/i18n/en.json'))
  assert.ok(messages.env.staging && messages.env.local)
})

test('no frontend reads an environment name for the label, and only the strip, the store and the start-up files touch the label', () => {
  const walk = (d) => fs.readdirSync(path.join(ROOT, d), { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(`${d}/${e.name}`) : [`${d}/${e.name}`]))
  const sources = ['platform/src', 'admin/src', 'ui/src'].flatMap(walk).filter((f) => /\.(ts|vue)$/.test(f))
  const allowed = ['EnvBanner.vue', 'envLabel.ts', 'App.vue', 'AdminApp.vue', 'main.ts', 'GateScreen.vue', 'gate.ts']
  for (const file of sources) {
    assert.doesNotMatch(read(file), /VITE_ENV_LABEL/, file) // the label is a SERVER setting (ENV_LABEL); the admin application reads one environment name only (hardening test)
    if (allowed.some((a) => file.endsWith(a))) continue
    assert.doesNotMatch(read(file), /envLabel|setEnvLabel/, file) // nothing else behaves differently because of it
  }
})
