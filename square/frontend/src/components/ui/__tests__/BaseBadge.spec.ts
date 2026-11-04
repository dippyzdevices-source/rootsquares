// Tests for BaseBadge (4 cases), e.g. BaseBadge; defaults to the neutral variant; applies success variant classes.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseBadge from '../BaseBadge.vue'

describe('BaseBadge', () => {
  it('defaults to the neutral variant', () => {
    const wrapper = mount(BaseBadge, { slots: { default: 'Default' } })

    expect(wrapper.classes()).toContain('text-text-secondary')
  })

  it('applies success variant classes', () => {
    const wrapper = mount(BaseBadge, { props: { variant: 'success' } })

    expect(wrapper.classes()).toContain('text-success')
  })

  it('applies error variant classes', () => {
    const wrapper = mount(BaseBadge, { props: { variant: 'error' } })

    expect(wrapper.classes()).toContain('text-error')
  })
})
