// Tests for BaseFileButton (3 cases), e.g. BaseFileButton; shows the slot label and forwards the native change event; disables the input.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseFileButton from '../BaseFileButton.vue'

describe('BaseFileButton', () => {
  it('shows the slot label and forwards the native change event', async () => {
    const wrapper = mount(BaseFileButton, { props: { accept: '.xlsx' }, slots: { default: 'Choose spreadsheet' } })
    expect(wrapper.text()).toContain('Choose spreadsheet')
    expect(wrapper.find('input').attributes('accept')).toBe('.xlsx')
    await wrapper.find('input').trigger('change')
    expect(wrapper.emitted('change')).toHaveLength(1)
  })

  it('disables the input', () => {
    const wrapper = mount(BaseFileButton, { props: { disabled: true } })
    expect(wrapper.find('input').attributes('disabled')).toBeDefined()
  })
})
