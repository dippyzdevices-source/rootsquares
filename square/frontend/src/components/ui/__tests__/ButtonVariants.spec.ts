// Tests for ButtonVariants (3 cases), e.g. button variants (design system danger / info); BaseButton renders danger and info classes; BaseIconButton renders danger/info, and maps primary->solid, secondary.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseButton from '../BaseButton.vue'
import BaseIconButton from '../BaseIconButton.vue'

describe('button variants (design system danger / info)', () => {
  it('BaseButton renders danger and info classes', () => {
    expect(mount(BaseButton, { props: { variant: 'danger' } }).classes()).toContain('ds-btn-danger')
    expect(mount(BaseButton, { props: { variant: 'info' } }).classes()).toContain('ds-btn-info')
    expect(mount(BaseButton, { props: { variant: 'success' } }).classes()).toContain('ds-btn-success')
    expect(mount(BaseButton, { props: { variant: 'warning' } }).classes()).toContain('ds-btn-warning')
    expect(mount(BaseIconButton, { props: { label: 'x', variant: 'success' } }).classes()).toContain('ds-icon-btn-success')
    expect(mount(BaseIconButton, { props: { label: 'x', variant: 'warning' } }).classes()).toContain('ds-icon-btn-warning')
  })

  it('BaseIconButton renders danger/info, and maps primary->solid, secondary->outline', () => {
    expect(mount(BaseIconButton, { props: { label: 'x', variant: 'danger' } }).classes()).toContain('ds-icon-btn-danger')
    expect(mount(BaseIconButton, { props: { label: 'x', variant: 'info' } }).classes()).toContain('ds-icon-btn-info')
    expect(mount(BaseIconButton, { props: { label: 'x', variant: 'primary' } }).classes()).toContain('ds-icon-btn-solid')
    expect(mount(BaseIconButton, { props: { label: 'x', variant: 'secondary' } }).classes()).toEqual(['ds-icon-btn'])
  })
})
