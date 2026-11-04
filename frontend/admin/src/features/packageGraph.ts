// The hierarchy of a custom package (W19-R25): every always-on part and every module is a node that may need other nodes (Settings needs Admin, Admin needs
// Sign-in, Tickets need Events, Payments, Admin and Member account ...). Pure functions, no screen: PackageBuilder.vue draws it in five views.
// The platform repeats the same rules on save (backend/app/platform/modules.py), so a screen that disagrees can never store a broken combination.

export interface PkgNode { id: string; name: string; desc: string; needs: string[]; core: boolean }
export interface PkgInfo extends PkgNode {
  deep: Set<string> // everything it needs, however far
  all: Set<string> // everything that needs it, however far
  lv: number // 0 = stands alone; otherwise one more than the highest level of what it needs
  direct: string[] // the needs that are not already needed through another need (what is drawn as a line)
}
export interface PkgGraph { info: Record<string, PkgInfo>; ids: string[] }

/** The nodes in the order the views show them: by level, then as given. */
export function buildGraph(nodes: PkgNode[]): PkgGraph {
  const known = new Set(nodes.map((n) => n.id))
  const info: Record<string, PkgInfo> = {}
  for (const n of nodes) info[n.id] = { ...n, needs: n.needs.filter((k) => known.has(k)), deep: new Set(), all: new Set(), lv: 0, direct: [] }
  const reach = (id: string, seen: Set<string>) => {
    for (const k of info[id]!.needs) if (!seen.has(k)) { seen.add(k); reach(k, seen) }
    return seen
  }
  for (const id of Object.keys(info)) info[id]!.deep = reach(id, new Set())
  for (const id of Object.keys(info)) for (const k of info[id]!.deep) info[k]!.all.add(id)
  const level = (id: string, path: string[] = []): number => {
    const n = info[id]!
    if (!n.needs.length || path.includes(id)) return 0
    return 1 + Math.max(...n.needs.map((k) => level(k, [...path, id])))
  }
  for (const id of Object.keys(info)) {
    const n = info[id]!
    n.lv = level(id)
    n.direct = n.needs.filter((k) => !n.needs.some((o) => o !== k && info[o]!.deep.has(k)))
  }
  const order = new Map(nodes.map((n, i) => [n.id, i]))
  const ids = nodes.map((n) => n.id).sort((a, b) => info[a]!.lv - info[b]!.lv || order.get(a)! - order.get(b)!)
  return { info, ids }
}

/** Switch `id` on together with everything it needs. Returns what was added besides `id`. */
export function switchOn(g: PkgGraph, on: Set<string>, id: string): string[] {
  const added = [...g.info[id]!.deep].filter((k) => !on.has(k))
  on.add(id)
  added.forEach((k) => on.add(k))
  return added
}

/** Switch `id` off together with everything that needs it. Returns what was removed besides `id`. */
export function switchOff(g: PkgGraph, on: Set<string>, id: string): string[] {
  const removed = [...g.info[id]!.all].filter((k) => on.has(k))
  on.delete(id)
  removed.forEach((k) => on.delete(k))
  return removed
}

/** The column or step (0 to 4) a node sits in: its level, with the deepest levels together. */
export const stepOf = (g: PkgGraph, id: string): number => Math.min(g.info[id]!.lv, 4)
