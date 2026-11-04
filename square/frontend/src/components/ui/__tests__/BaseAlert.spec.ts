// Tests for BaseAlert (5 cases), e.g. BaseAlert; has role="alert" for accessibility; defaults to the info variant.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseAlert from '../BaseAlert.vue'

describe('BaseAlert', () => {
  it('has role="alert" for accessibility', () => {
    const wrapper = mount(BaseAlert)

    expect(wrapper.attributes('role')).toBe('alert')
  })

  it('defaults to the info variant', () => {
    const wrapper = mount(BaseAlert, { slots: { default: 'Heads up' } })

    expect(wrapper.classes()).toContain('bg-surface')
  })

  it('applies success variant classes', () => {
    const wrapper = mount(BaseAlert, { props: { variant: 'success' } })

    expect(wrapper.classes()).toContain('text-success')
  })

  it('applies error variant classes', () => {
    const wrapper = mount(BaseAlert, { props: { variant: 'error' } })

    expect(wrapper.classes()).toContain('text-error')
  })
})
