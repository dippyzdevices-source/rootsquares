// Tests for lookOf in previewBridge.ts (the data of an rs-preview-look message): what it accepts and what it drops.
// Run from square/frontend: npx vitest run src/dev/previewBridge.spec.ts
import { describe, expect, it } from 'vitest'
import { lookOf } from './previewBridge'

describe('lookOf', () => {
  it('keeps strings only and returns null for nothing', () => {
    expect(lookOf({ colors: { bg: '#fff', ink: '#000', acc: '#f00' }, fonts: 'soft' })).toEqual({ colors: { bg: '#fff', ink: '#000', acc: '#f00' }, fonts: 'soft' })
    expect(lookOf({ colors: null, fonts: null })).toBeNull()
    expect(lookOf({})).toBeNull()
  })
  it('drops a colour object with a missing or non-string part and a non-string font', () => {
    expect(lookOf({ colors: { bg: '#fff', ink: 5, acc: '#f00' }, fonts: 3 })).toBeNull()
    expect(lookOf({ colors: { bg: '#fff' }, fonts: 'bold' })).toEqual({ colors: null, fonts: 'bold' })
    expect(lookOf({ colors: 'red' })).toBeNull()
  })
})
