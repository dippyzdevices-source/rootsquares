// Minimal custom-property cascade for the scoped theme tests (no CSS engine in the project, no new dependencies).
// Supports the selectors the token files use: :root, html, and attribute selectors combined in one compound ([a="x"][b="y"]).
// Anything else (descendants, classes, :has, at-rules) is ignored, because it never defines the custom properties tested here.
import { readFileSync } from 'node:fs'

export function parseRules(file) {
  const css = readFileSync(file, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
  const rules = []
  let order = 0
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const decls = {}
    for (const d of m[2].matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);?/gi)) decls[d[1]] = d[2].trim().replace(/\s+/g, ' ')
    if (!Object.keys(decls).length) continue
    for (const sel of m[1].split(',')) {
      const compound = parseCompound(sel.trim())
      if (compound) rules.push({ ...compound, decls, order: order++ })
    }
  }
  return rules
}

function parseCompound(sel) {
  if (!sel || /[\s>+~.#]/.test(sel.replace(/\[[^\]]*\]/g, ''))) return null // descendant, class, id, combinators
  let rest = sel
  const attrs = []
  let root = false
  let tag = null
  const head = rest.match(/^(:root|html)/)
  if (head) { if (head[1] === ':root') root = true; else tag = 'html'; rest = rest.slice(head[1].length) }
  while (rest) {
    const a = rest.match(/^\[([a-z-]+)(?:="([^"]*)")?\]/)
    if (!a) return null // pseudo-classes such as :has() or :where()
    attrs.push([a[1], a[2] ?? null])
    rest = rest.slice(a[0].length)
  }
  return { attrs, root, tag, specificity: attrs.length * 10 + (root ? 10 : 0) + (tag ? 1 : 0) }
}

const matches = (r, el) =>
  (!r.root || el.root) && (!r.tag || el.tag === r.tag) && r.attrs.every(([k, v]) => k in el.attrs && (v === null || el.attrs[k] === v))

/** chain: [{tag, root?, attrs}] from the root element down to the element of interest. Returns resolved custom properties of the last one. */
export function resolve(rulesets, chain) {
  let props = {}
  for (const el of chain) {
    const own = {}
    const hits = rulesets.flat().filter((r) => matches(r, el)).sort((a, b) => a.specificity - b.specificity || a.order - b.order)
    for (const r of hits) Object.assign(own, r.decls)
    props = { ...props, ...own } // custom properties inherit; a match on a descendant overrides
  }
  return props
}
