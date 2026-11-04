import { squareProfile, type PhoneRule } from '../services/squareConfig'

// The phone number rule of the square (rootsquares W6-R52): bca-oslo accepted only Norwegian mobile numbers. The rule comes from the server
// (/api/square/config), the same one the backend checks with (app/common/phone.py), so the forms and the server cannot disagree.

/** What a phone field starts with, e.g. "+47 ". */
export function phonePrefix(rule: PhoneRule = squareProfile.phone): string {
  return `+${rule.dial} `
}

/** True for an empty field or one that holds only the calling code. */
export function isBlankPhone(phone: string, rule: PhoneRule = squareProfile.phone): boolean {
  const text = phone.trim()
  return text === '' || text === `+${rule.dial}`
}

export function phoneMessage(rule: PhoneRule = squareProfile.phone): string {
  const length = rule.min_digits === rule.max_digits ? `${rule.min_digits}` : `${rule.min_digits} to ${rule.max_digits}`
  return `Enter a valid phone number for ${rule.name} (+${rule.dial}, ${length} digits).`
}

export function isValidPhone(phone: string, rule: PhoneRule = squareProfile.phone): boolean {
  const text = phone.trim()
  let digits = text.replace(/\D/g, '')
  if (text.startsWith('+')) {
    if (!digits.startsWith(rule.dial)) return false
    digits = digits.slice(rule.dial.length)
  } else if (digits.startsWith(`00${rule.dial}`)) {
    digits = digits.slice(2 + rule.dial.length)
  } else if (digits.startsWith(rule.dial) && rule.min_digits === rule.max_digits && digits.length === rule.dial.length + rule.max_digits) {
    digits = digits.slice(rule.dial.length) // the calling code written without "+"
  }
  if (rule.trunk_zero && digits.startsWith('0')) digits = digits.slice(1)
  return digits.length >= rule.min_digits && digits.length <= rule.max_digits
}
