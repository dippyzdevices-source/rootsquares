import { computed, onMounted, ref, type Ref } from 'vue'
import { fetchLookup, type LookupItem } from '../services/lookupsApi'
import { humanize } from '../utils/formatEnum'

// Option lists driven by the backend `lookup_values` table. One shared ref per list so every
// component on a page reuses a single fetch; `invalidateLookup` forces a refetch after an edit.
const cache = new Map<string, Ref<LookupItem[]>>()
const loaded = new Set<string>()

function listRef(key: string) {
  let r = cache.get(key)
  if (!r) {
    r = ref<LookupItem[]>([])
    cache.set(key, r)
  }
  return r
}

async function load(key: string) {
  const r = listRef(key)
  try {
    r.value = await fetchLookup(key)
    loaded.add(key)
  } catch {
    // Leave whatever we have; labels fall back to humanized values and the picker stays empty.
  }
}

export function invalidateLookup(key: string) {
  loaded.delete(key)
}

export function useLookup(key: string) {
  const options = listRef(key)
  onMounted(() => {
    if (!loaded.has(key)) void load(key)
  })
  /** Display label for a stored value (also works for retired values no longer in `options`).
   *  A missing value (e.g. a free order with no payment method) shows a dash, never an error. */
  function label(value: string | null | undefined): string {
    if (value == null || value === '') return '—'
    return options.value.find((o) => o.value === value)?.label ?? humanize(value)
  }
  /** The listed values only, in the given order, with their current labels — for filters that
   *  offer just some of a list's values. */
  function pick(values: string[]) {
    return computed(() => values.map((v) => ({ value: v, label: label(v) })))
  }
  return { options, label, pick }
}
