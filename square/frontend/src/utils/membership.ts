import { withCurrency } from './money'

export type BillingFrequency = 'monthly' | 'quarterly' | 'yearly'

const FREQUENCY_LABELS: Record<BillingFrequency, string> = {
  monthly: 'month',
  quarterly: 'quarter',
  yearly: 'year',
}

// e.g. "500 kr / month". Prefer this over "Contact us for pricing" whenever
// contact_for_price is true — see formatMembershipPrice for that combined decision.
export function frequencyLabel(frequency: BillingFrequency): string {
  return FREQUENCY_LABELS[frequency]
}

export function formatMembershipPrice(type: {
  price: number | null
  billing_frequency: BillingFrequency
  contact_for_price: boolean
}): string {
  if (type.contact_for_price || type.price === null) return 'Contact us for pricing'
  return `${withCurrency(String(type.price))} / ${frequencyLabel(type.billing_frequency)}`
}
