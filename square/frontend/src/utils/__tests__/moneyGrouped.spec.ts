// Tests for moneyGrouped (3 cases), e.g. grouped money formats; puts a (non-breaking) space between the thousands; leaves small amounts alone and keeps the sign.
import { describe, it, expect } from 'vitest'
import { formatPriceGrouped, formatPriceRoundedGrouped } from '../money'

const nb = (s: string) => s.replace(/\u00a0/g, ' ')

describe('grouped money formats', () => {
  it('puts a (non-breaking) space between the thousands', () => {
    expect(nb(formatPriceRoundedGrouped(7160600))).toBe('71 606 kr')
    expect(nb(formatPriceGrouped(2836100))).toBe('28 361.00 kr')
    expect(formatPriceRoundedGrouped(7160600)).toContain('\u00a0')
  })

  it('leaves small amounts alone and keeps the sign', () => {
    expect(formatPriceRoundedGrouped(99900)).toBe('999 kr')
    expect(formatPriceGrouped(5)).toBe('0.05 kr')
    expect(nb(formatPriceRoundedGrouped(-4250000))).toBe('-42 500 kr')
    expect(formatPriceRoundedGrouped(0)).toBe('0 kr')
  })
})
