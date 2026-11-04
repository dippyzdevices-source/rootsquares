// Pricing helpers and the list of plans. **No amount lives here** (W14-R29): every price is data on the platform (the table `plan_prices`, set on the owner console Prices page),
// read through src/services/prices.ts. Money is integer minor units (cents) plus a currency; the list is in US dollars only.
export const PRICE_CURRENCY = 'USD'

export interface LaunchPackage { id: 'roots' | 'square' | 'grove'; highlighted?: boolean }
export const LAUNCH_PACKAGES: LaunchPackage[] = [{ id: 'roots' }, { id: 'square', highlighted: true }, { id: 'grove' }]

export interface RunningPlan { id: 'keep' | 'live' | 'event'; highlighted?: boolean }
export const RUNNING_PLANS: RunningPlan[] = [{ id: 'keep' }, { id: 'live', highlighted: true }, { id: 'event' }]
export const EVENT_PASS_DAYS = 45 // live days; then 45 days of archive, then deleted (ADR 044)

/** A price that includes `percent` tax, split into the amount without it and the tax (W13-R51): $149 at 25% is $119.20 + $29.80. */
export function taxSplit(minor: number, percent: number): { net: number; tax: number } {
  const net = percent > 0 ? Math.round((minor * 100) / (100 + percent)) : minor
  return { net, tax: minor - net }
}

/** Whole dollars when there are no cents ($149), else with cents. */
export function usd(minor: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: PRICE_CURRENCY, minimumFractionDigits: minor % 100 === 0 ? 0 : 2, maximumFractionDigits: 2 }).format(minor / 100)
}
