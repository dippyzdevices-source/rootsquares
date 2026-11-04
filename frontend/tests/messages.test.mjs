// A text in an i18n file may not hold a bare "@" (run: npm run test:messages). vue-i18n reads "@" as the start of a linked message, so
// "tickets@club.org" or "the @" stops the whole component with "Message compilation error" and the page shows nothing (W25-R28). Write "{'@'}" instead.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const FILES = ['platform/src/i18n/en.json', 'admin/src/i18n/admin.en.json', 'ui/src/i18n/en.json']

function* strings(value, path) {
  if (typeof value === 'string') yield [path, value]
  else if (value && typeof value === 'object') for (const [k, v] of Object.entries(value)) yield* strings(v, path ? `${path}.${k}` : k)
}

for (const file of FILES) {
  test(`no bare @ in the messages of ${file}`, () => {
    const bad = []
    for (const [path, text] of strings(JSON.parse(readFileSync(new URL(`../${file}`, import.meta.url), 'utf8')), '')) {
      if (text.split("{'@'}").join('').includes('@')) bad.push(`${path}: ${text.slice(0, 80)}`)
    }
    assert.deepEqual(bad, [], `write {'@'} instead of @ in:\n${bad.join('\n')}`)
  })
}
