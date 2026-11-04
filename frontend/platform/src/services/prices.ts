// The platform's prices, read once and shared (W14-R29). **No amount is written anywhere in the code**: every price is a row of `plan_prices` that a platform admin sets
// on the owner console Prices page. A price that is not set reads as `null` and the page shows a dash instead of a number.
import { ref } from 'vue'
import { usd } from '@rootsquares/ui/mock/pricing'
import { platform } from './platform'

export const prices = ref<Record<string, number>>({})
export const pricesState = ref<'idle' | 'loading' | 'ready' | 'failed'>('idle')
let pending: Promise<void> | null = null

export function loadPrices(force = false): Promise<void> {
  if (pending && !force) return pending
  pricesState.value = 'loading'
  pending = platform.getPrices().then(
    (rows) => { prices.value = Object.fromEntries(rows.map((p) => [p.key, p.amount_minor])); pricesState.value = 'ready' },
    () => { pricesState.value = 'failed'; pending = null },
  )
  return pending
}

/** The price in cents, or null when it is not set (or not loaded yet). */
export const minorOf = (key: string): number | null => prices.value[key] ?? null
/** The price as dollars ("$149"), or a dash when it is not set. */
export const moneyOf = (key: string): string => (minorOf(key) === null ? '—' : usd(minorOf(key)!))
