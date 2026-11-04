// Choosing the owner's country fills in the square's currency and phone country (W14-R31). They are only suggestions: both stay changeable, and a country with no
// match here leaves the fields as they are. Every currency named here must be in CURRENCIES of services/platform.ts (a test checks it); no imports, so a node test can load this file.
const CURRENCY_OF: Record<string, string> = {
  NO: 'NOK', SE: 'SEK', DK: 'DKK', IS: 'ISK', GB: 'GBP', US: 'USD',
  // the euro countries
  FI: 'EUR', DE: 'EUR', IE: 'EUR', NL: 'EUR', FR: 'EUR', AT: 'EUR', BE: 'EUR', ES: 'EUR', IT: 'EUR', PT: 'EUR', GR: 'EUR', LU: 'EUR', MT: 'EUR', CY: 'EUR',
  SK: 'EUR', SI: 'EUR', EE: 'EUR', LV: 'EUR', LT: 'EUR', HR: 'EUR',
}

export function currencyFor(country: string): string {
  return CURRENCY_OF[country.toUpperCase()] ?? ''
}

/** The phone country to suggest: the same country when the form offers it (`offered` is PHONE_COUNTRIES), else nothing. */
export function phoneCountryFor(country: string, offered: readonly string[]): string {
  const c = country.toUpperCase()
  return offered.includes(c) ? c : ''
}
