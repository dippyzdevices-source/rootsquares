// Tests for phone (3 cases), e.g. phone rule; is Norway (bca-oslo) by default; follows another square's country.
import { describe, expect, it } from 'vitest'
import { isBlankPhone, isValidPhone, phoneMessage, phonePrefix } from './phone'
import type { PhoneRule } from '../services/squareConfig'

const GB: PhoneRule = { country: 'GB', name: 'United Kingdom', dial: '44', min_digits: 9, max_digits: 10, trunk_zero: true }

describe('phone rule', () => {
  it('is Norway (bca-oslo) by default', () => {
    expect(phonePrefix()).toBe('+47 ')
    expect(isValidPhone('+47 412 34 567')).toBe(true)
    expect(isValidPhone('41234567')).toBe(true)
    expect(isValidPhone('004741234567')).toBe(true)
    expect(isValidPhone('4741234567')).toBe(true)
    expect(isValidPhone('4123456')).toBe(false)
    expect(isValidPhone('+46 70 123 45 67')).toBe(false)
    expect(isBlankPhone('+47')).toBe(true)
    expect(isBlankPhone('+47 ')).toBe(true)
    expect(isBlankPhone('+47 4')).toBe(false)
    expect(phoneMessage()).toBe('Enter a valid phone number for Norway (+47, 8 digits).')
  })

  it("follows another square's country", () => {
    expect(phonePrefix(GB)).toBe('+44 ')
    expect(isValidPhone('+44 7700 900123', GB)).toBe(true)
    expect(isValidPhone('07700 900123', GB)).toBe(true)
    expect(isValidPhone('+47 41234567', GB)).toBe(false)
    expect(phoneMessage(GB)).toBe('Enter a valid phone number for United Kingdom (+44, 9 to 10 digits).')
  })
})
