// Tests for BaseLoadingState (3 cases), e.g. BaseLoadingState; shows the passed label alongside one of the design-system motif spinne; falls back to a generic label when none is passed.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseLoadingState from '../BaseLoadingState.vue'
import { SPINNER_VARIANTS } from '../../../utils/spinner'

describe('BaseLoadingState', () => {
  it('shows the passed label alongside one of the design-system motif spinners', () => {
    const wrapper = mount(BaseLoadingState, { props: { label: 'Loading your dashboard…' } })

    expect(wrapper.text()).toContain('Loading your dashboard…')
    const spinner = wrapper.findComponent({ name: 'BaseSpinner' })
    expect(spinner.exists()).toBe(true)
    expect(SPINNER_VARIANTS).toContain(spinner.props('variant'))
    expect(spinner.props('size')).toBe('xl')
  })

  it('falls back to a generic label when none is passed', () => {
    const wrapper = mount(BaseLoadingState)

    expect(wrapper.text()).toContain('Loading…')
  })
})
