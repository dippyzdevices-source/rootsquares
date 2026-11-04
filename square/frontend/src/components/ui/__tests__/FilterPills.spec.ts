// Tests for FilterPills (2 cases), e.g. FilterPills; marks the chosen pill and emits the new value when another is clicked.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FilterPills from '../FilterPills.vue'

const options = [
  { value: 'all', label: 'All' },
  { value: 'live', label: 'Live' },
]

describe('FilterPills', () => {
  it('marks the chosen pill and emits the new value when another is clicked', async () => {
    const wrapper = mount(FilterPills, { props: { modelValue: 'all', options, label: 'Filter by status' } })
    const pills = wrapper.findAll('button.ds-tag')
    expect(pills.map((p) => p.text())).toEqual(['All', 'Live'])
    expect(pills[0].classes()).toContain('ds-tag-selected')
    expect(pills[0].attributes('aria-pressed')).toBe('true')
    expect(wrapper.attributes('aria-label')).toBe('Filter by status')

    await pills[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['live']])
  })
})
