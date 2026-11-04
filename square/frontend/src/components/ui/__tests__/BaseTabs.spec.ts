// Tests for BaseTabs (5 cases), e.g. BaseTabs; renders one tab button per tab; marks the tab matching modelValue as selected.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseTabs from '../BaseTabs.vue'

const tabs = [
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'past', label: 'Past' },
]

describe('BaseTabs', () => {
  it('renders one tab button per tab', () => {
    const wrapper = mount(BaseTabs, { props: { modelValue: 'upcoming', tabs } })

    expect(wrapper.findAll('[role="tab"]')).toHaveLength(2)
  })

  it('marks the tab matching modelValue as selected', () => {
    const wrapper = mount(BaseTabs, { props: { modelValue: 'past', tabs } })

    const [upcomingTab, pastTab] = wrapper.findAll('[role="tab"]')
    expect(upcomingTab.attributes('aria-selected')).toBe('false')
    expect(pastTab.attributes('aria-selected')).toBe('true')
  })

  it('emits update:modelValue with the clicked tab id', async () => {
    const wrapper = mount(BaseTabs, { props: { modelValue: 'upcoming', tabs } })

    await wrapper.findAll('[role="tab"]')[1].trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['past']])
  })

  it('renders only the slot matching the active tab', () => {
    const wrapper = mount(BaseTabs, {
      props: { modelValue: 'upcoming', tabs },
      slots: {
        upcoming: '<p>Upcoming content</p>',
        past: '<p>Past content</p>',
      },
    })

    expect(wrapper.text()).toContain('Upcoming content')
    expect(wrapper.text()).not.toContain('Past content')
  })
})
