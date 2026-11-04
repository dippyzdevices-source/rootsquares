// Guard: wording that belongs to an admin-managed lookup list must not be hand-typed again.
// If a page needs the options of a lookup list, it uses useLookup('<list_key>') (composables/) —
// never `{ value: 'x', label: 'X' }` literals copied from the list's defaults. The expected
// pairs come from test-utils/lookupDefaults.ts (kept equal to the backend registry by a backend test).
import { describe, it, expect } from 'vitest'
import { LOOKUP_DEFAULTS } from '../test-utils/lookupDefaults'

const raw = import.meta.glob(['../**/*.vue', '../**/*.ts'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>
const files = Object.entries(raw)
  .map(([key, text]) => ({ path: key.replace(/^\.\.\//, ''), text }))
  .filter((f) => !f.path.includes('__tests__') && !f.path.startsWith('test-utils/') && f.path !== 'test-setup.ts' && !f.path.endsWith('.spec.ts'))

const pairs = Object.entries(LOOKUP_DEFAULTS).flatMap(([list, items]) =>
  items.map((i) => ({ list, re: new RegExp(`value: '${i.value}', label: '${i.label.replace(/[.*+?^${}()|[\]\/]/g, '\$&')}'`) })),
)

// Filter-pill / toolbar vocabulary that happens to equal a list's wording (a UI filter such as
// Draft/Published, not the list itself). Must match reality exactly so it can only shrink.
const UI_VOCABULARY = new Set<string>(['pages/admin/AdminGalleryListView.vue', 'pages/admin/AdminMagazinesListView.vue', 'pages/admin/AdminDonationsView.vue', 'demo/fixtures.ts' /* neutral demo sample data */])

describe('lookup wording is not hand-typed', () => {
  const offenders = files
    .map((f) => {
      const byList = new Map<string, number>()
      for (const p of pairs) if (p.re.test(f.text)) byList.set(p.list, (byList.get(p.list) ?? 0) + 1)
      // Two or more pairs of the same list in one file = a copied option array (a single shared
      // word such as "Active" or "Other" is just vocabulary).
      return { path: f.path, hits: [...byList].filter(([, n]) => n >= 2).map(([list]) => list) }
    })
    .filter((f) => f.hits.length > 0)

  it('no page hard-codes the wording of a lookup list', () => {
    const unexpected = offenders.filter((o) => !UI_VOCABULARY.has(o.path)).map((o) => `${o.path} (${[...new Set(o.hits)].join(', ')})`)
    expect(unexpected, 'use useLookup(<list_key>) instead of typing these options').toEqual([])
  })

  it('UI_VOCABULARY lists only files that still hand-type something', () => {
    const stale = [...UI_VOCABULARY].filter((p) => !offenders.some((o) => o.path === p))
    expect(stale, 'remove these from UI_VOCABULARY').toEqual([])
  })
})
