import { squareProfile } from '../services/squareConfig'

// Money is always stored/transmitted as an integer in minor units (øre, cents) — never a float.
// The text uses the square's own currency (rootsquares W6-R47; bca-oslo wrote every amount as "kr").
const KRONE_CURRENCIES = ['NOK', 'SEK', 'DKK', 'ISK'] // written "250.00 kr"
const SYMBOLS: Record<string, string> = { EUR: '€', GBP: '£', USD: '$' } // written "€250.00"

/** `text` is the number as already formatted ("250.00", "250"); this only adds the currency the way people write it. */
export function withCurrency(text: string, currency: string = squareProfile.currency): string {
  if (KRONE_CURRENCIES.includes(currency)) return `${text} kr`
  if (SYMBOLS[currency]) return `${SYMBOLS[currency]}${text}`
  return `${text} ${currency}`
}

export function formatPrice(minorUnits: number): string {
  return withCurrency((minorUnits / 100).toFixed(2))
}

// Same conversion as formatPrice, but rounded to the nearest whole unit with no decimal
// places — for summary/dashboard displays where exact precision isn't the point.
export function formatPriceRounded(minorUnits: number): string {
  return withCurrency(String(Math.round(minorUnits / 100)))
}

const NBSP = '\u00a0'

// Same figures with a space between the thousands ("71 606 kr", "28 361.00 kr") - for the
// accounting page, where the amounts get big. The space is non-breaking so an amount never wraps.
function group(whole: string): string {
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP)
}

export function formatPriceGrouped(minorUnits: number): string {
  const [whole, decimals] = (Math.abs(minorUnits) / 100).toFixed(2).split('.')
  return `${minorUnits < 0 ? '-' : ''}${group(whole)}.${decimals} kr`
}

export function formatPriceRoundedGrouped(minorUnits: number): string {
  const rounded = Math.round(Math.abs(minorUnits) / 100)
  return `${minorUnits < 0 && rounded ? '-' : ''}${group(String(rounded))} kr`
}

export function toMinorUnits(kroner: string): number {
  const parsed = parseFloat(kroner)
  return Number.isFinite(parsed) ? Math.round(parsed * 100) : 0
}

export function fromMinorUnits(minorUnits: number): string {
  return (minorUnits / 100).toFixed(2)
}
