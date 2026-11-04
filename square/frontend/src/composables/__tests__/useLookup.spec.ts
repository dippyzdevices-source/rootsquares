// Tests for useLookup (4 cases), e.g. useLookup().label; shows the list wording for a known value (the test setup serves the de; falls back to a readable version of an unknown value.
import { describe, it, expect } from 'vitest'
import { defineComponent } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useLookup } from '../useLookup'

function labelOf(key: string) {
  let label!: (value: string | null | undefined) => string
  const wrapper = mount(
    defineComponent({
      setup() {
        label = useLookup(key).label
        return () => null
      },
    }),
  )
  return { label, wrapper }
}

describe('useLookup().label', () => {
  it('shows the list wording for a known value (the test setup serves the default lists)', async () => {
    const { label } = labelOf('payment_provider')
    await flushPromises()
    expect(label('vipps_qr')).toBe('Vipps-QR')
  })

  it('falls back to a readable version of an unknown value', () => {
    const { label } = labelOf('payment_provider')
    expect(label('some_old_value')).toBe('Some old value')
  })

  it('shows a dash — and never throws — when there is no value (e.g. a free order has no payment method)', () => {
    const { label } = labelOf('payment_provider')
    expect(label(null)).toBe('—')
    expect(label(undefined)).toBe('—')
    expect(label('')).toBe('—')
  })
})
