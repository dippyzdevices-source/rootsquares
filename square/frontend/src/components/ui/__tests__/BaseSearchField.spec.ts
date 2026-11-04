// Tests for BaseSearchField (4 cases), e.g. BaseSearchField; emits the typed value and forwards attrs (aria-label, keyup.enter) to; shows a clear button only when there is text, and Escape or the button.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseSearchField from '../BaseSearchField.vue'

describe('BaseSearchField', () => {
  it('emits the typed value and forwards attrs (aria-label, keyup.enter) to the input', async () => {
    let entered = 0
    const wrapper = mount(BaseSearchField, {
      props: { modelValue: '' },
      attrs: { 'aria-label': 'Search events', onKeyup: () => entered++ },
    })
    const input = wrapper.find('input')
    expect(input.attributes('aria-label')).toBe('Search events')
    await input.setValue('saraswati')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['saraswati'])
    await input.trigger('keyup', { key: 'Enter' })
    expect(entered).toBe(1)
  })

  it('shows a clear button only when there is text, and Escape or the button clears', async () => {
    const empty = mount(BaseSearchField, { props: { modelValue: '' } })
    expect(empty.find('.base-search-clear').exists()).toBe(false)

    const wrapper = mount(BaseSearchField, { props: { modelValue: 'abc' } })
    await wrapper.find('.base-search-clear').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([''])
    await wrapper.find('input').trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([''])
  })

  it('keeps class and style on the root (so .ds-toolbar-search sizes the whole field) and other attrs on the input', () => {
    const wrapper = mount(BaseSearchField, {
      props: { modelValue: '' },
      attrs: { class: 'ds-toolbar-search', style: 'max-width: 420px', 'aria-label': 'Search' },
    })
    expect(wrapper.classes()).toContain('ds-toolbar-search')
    expect(wrapper.attributes('style')).toContain('max-width')
    const input = wrapper.find('input')
    expect(input.classes()).not.toContain('ds-toolbar-search')
    expect(input.attributes('aria-label')).toBe('Search')
  })
})
