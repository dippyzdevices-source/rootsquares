// Tests for filterParams (4 cases), e.g. listParam; joins several values with commas; keeps a single value as it is.
import { describe, it, expect } from 'vitest'
import { listParam } from '../filterParams'

describe('listParam', () => {
  it('joins several values with commas', () => {
    expect(listParam(['paid', 'pending'])).toBe('paid,pending')
    expect(listParam([3, 4])).toBe('3,4')
  })
  it('keeps a single value as it is', () => {
    expect(listParam('paid')).toBe('paid')
    expect(listParam(7)).toBe('7')
  })
  it('means no filter for empty input', () => {
    expect(listParam([])).toBeUndefined()
    expect(listParam('')).toBeUndefined()
    expect(listParam(undefined)).toBeUndefined()
    expect(listParam(null)).toBeUndefined()
  })
})
