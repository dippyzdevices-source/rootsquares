// Tests for BaseMultiSelect (7 cases), e.g. BaseMultiSelect; reads the all-label when nothing is ticked, the name for one, and a co; lists every option with a checkbox and keeps the menu open while ticki.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseMultiSelect from '../BaseMultiSelect.vue'
import { toggleOption, selectedLabel, optionLabels } from '../../../test-utils/baseSelect'

const options = [
  { value: 'a', label: 'Adult' },
  { value: 'b', label: 'Child' },
  { value: 'c', label: 'Senior' },
]

function mountIt(modelValue: string[] = []) {
  return mount(BaseMultiSelect, { props: { modelValue, options, allLabel: 'All ticket types' } })
}

describe('BaseMultiSelect', () => {
  it('reads the all-label when nothing is ticked, the name for one, and a count for several', () => {
    expect(selectedLabel(mountIt())).toBe('All ticket types')
    expect(selectedLabel(mountIt(['b']))).toBe('Child')
    expect(selectedLabel(mountIt(['a', 'c']))).toBe('2 selected')
  })

  it('lists every option with a checkbox and keeps the menu open while ticking', async () => {
    const wrapper = mountIt()
    await toggleOption(wrapper, 'a')
    expect(optionLabels(wrapper)).toEqual(['Adult', 'Child', 'Senior'])
    expect(wrapper.find('.base-select-menu').exists()).toBe(true)
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['a']])
    expect(wrapper.emitted('change')?.[0]).toEqual([['a']])
  })

  it('adds to and removes from the ticked values', async () => {
    const wrapper = mountIt(['a'])
    await toggleOption(wrapper, 'b')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['a', 'b']])
    await wrapper.setProps({ modelValue: ['a', 'b'] })
    await toggleOption(wrapper, 'a')
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([['b']])
  })

  it('clears everything with the Clear link, shown only when something is ticked', async () => {
    const wrapper = mountIt(['a', 'b'])
    await wrapper.find('.base-select-button').trigger('click')
    await wrapper.find('.base-multiselect-clear').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([[]])

    const empty = mountIt()
    await empty.find('.base-select-button').trigger('click')
    expect(empty.find('.base-multiselect-clear').exists()).toBe(false)
  })

  it('works from the keyboard: arrows move, Space ticks, Escape closes', async () => {
    const wrapper = mountIt()
    const button = wrapper.find('.base-select-button')
    await button.trigger('keydown', { key: 'ArrowDown' }) // opens
    await button.trigger('keydown', { key: 'ArrowDown' })
    await button.trigger('keydown', { key: ' ' })
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['b']])
    await button.trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('.base-select-menu').exists()).toBe(false)
  })

  it('tints the button only when something is ticked and highlight-active is on', () => {
    const on = mount(BaseMultiSelect, { props: { modelValue: ['a'], options, highlightActive: true } })
    expect(on.classes()).toContain('base-select-active')
    const off = mount(BaseMultiSelect, { props: { modelValue: [], options, highlightActive: true } })
    expect(off.classes()).not.toContain('base-select-active')
  })
})
