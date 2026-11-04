// Tests for BaseSelect (6 cases), e.g. BaseSelect; shows the selected label, or the placeholder when nothing matches; opens, lists options with counts, and emits update + change when one i.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseSelect from '../BaseSelect.vue'
import { chooseOption, selectedLabel, optionLabels } from '../../../test-utils/baseSelect'

const options = [
  { value: 'all', label: 'All statuses' },
  { value: 'paid', label: 'Paid', count: 31 },
  { value: 'failed', label: 'Failed' },
]

describe('BaseSelect', () => {
  it('shows the selected label, or the placeholder when nothing matches', () => {
    expect(selectedLabel(mount(BaseSelect, { props: { modelValue: 'paid', options } }))).toBe('Paid')
    expect(selectedLabel(mount(BaseSelect, { props: { modelValue: '', options, placeholder: 'Choose' } }))).toBe('Choose')
  })

  it('opens, lists options with counts, and emits update + change when one is chosen', async () => {
    const wrapper = mount(BaseSelect, { props: { modelValue: 'all', options } })
    await wrapper.find('.base-select-button').trigger('click')
    expect(optionLabels(wrapper)).toEqual(['All statuses', 'Paid', 'Failed'])
    expect(wrapper.find('.base-select-option-count').text()).toBe('31')
    await chooseOption(wrapper, 'failed')
    expect(wrapper.emitted('update:modelValue')).toEqual([['failed']])
    expect(wrapper.emitted('change')).toEqual([['failed']])
    expect(wrapper.find('.base-select-menu').exists()).toBe(false)
  })

  it('does not emit when the current option is picked again', async () => {
    const wrapper = mount(BaseSelect, { props: { modelValue: 'paid', options } })
    await chooseOption(wrapper, 'paid')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('tints the control for a non-default choice when highlightActive is on', () => {
    expect(mount(BaseSelect, { props: { modelValue: 'paid', options, highlightActive: true } }).classes()).toContain('base-select-active')
    expect(mount(BaseSelect, { props: { modelValue: 'all', options, highlightActive: true } }).classes()).not.toContain('base-select-active')
  })

  it('supports the keyboard: arrows move, Enter chooses, Escape closes', async () => {
    const wrapper = mount(BaseSelect, { props: { modelValue: 'all', options } })
    const button = wrapper.find('.base-select-button')
    await button.trigger('keydown', { key: 'ArrowDown' })
    await button.trigger('keydown', { key: 'ArrowDown' })
    await button.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toEqual([['paid']])
    await button.trigger('keydown', { key: 'ArrowDown' })
    await button.trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('.base-select-menu').exists()).toBe(false)
  })
})
