// Tests for money (3 cases), e.g. money text; writes amounts in kroner by default; writes the other currencies the way people write them.
import { describe, it, expect } from 'vitest'
import { formatMembershipPrice } from '../membership'
import { formatPrice, formatPriceRounded, withCurrency } from '../money'

// The square's currency (squareProfile.currency) is NOK in the test suite; withCurrency takes any other explicitly (rootsquares W6-R47).
describe('money text', () => {
  it('writes amounts in kroner by default', () => {
    expect(formatPrice(25000)).toBe('250.00 kr')
    expect(formatPriceRounded(25049)).toBe('250 kr')
    expect(formatMembershipPrice({ price: 500, billing_frequency: 'monthly', contact_for_price: false })).toBe('500 kr / month')
  })

  it('writes the other currencies the way people write them', () => {
    expect(withCurrency('250.00', 'SEK')).toBe('250.00 kr')
    expect(withCurrency('250.00', 'DKK')).toBe('250.00 kr')
    expect(withCurrency('250.00', 'EUR')).toBe('€250.00')
    expect(withCurrency('250.00', 'GBP')).toBe('£250.00')
    expect(withCurrency('250.00', 'USD')).toBe('$250.00')
    expect(withCurrency('250.00', 'JPY')).toBe('250.00 JPY')
  })
})
