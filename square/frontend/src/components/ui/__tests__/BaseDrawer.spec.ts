// Tests for BaseDrawer (6 cases), e.g. BaseDrawer; does not render when modelValue is false; positions on the right by default.
import { describe, it, expect, afterEach } from 'vitest'
import { DOMWrapper, mount, type VueWrapper } from '@vue/test-utils'
import BaseDrawer from '../BaseDrawer.vue'

// BaseDrawer renders via <Teleport to="body">, so its content lives outside the
// mounted wrapper's own subtree — query document.body directly (the documented
// Vue Test Utils pattern for teleported content), not wrapper.find(). Each test
// also unmounts explicitly, since teleported nodes escape into the shared
// document.body and would otherwise leak into later tests in this file.
const body = () => new DOMWrapper(document.body)

let wrapper: VueWrapper | undefined

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

describe('BaseDrawer', () => {
  it('does not render when modelValue is false', () => {
    wrapper = mount(BaseDrawer, { props: { modelValue: false } })

    expect(body().find('[aria-label="Close"]').exists()).toBe(false)
  })

  it('positions on the right by default', () => {
    wrapper = mount(BaseDrawer, { props: { modelValue: true } })

    expect(body().find('.right-0').exists()).toBe(true)
    expect(body().find('.left-0').exists()).toBe(false)
  })

  it('positions on the left when side is "left"', () => {
    wrapper = mount(BaseDrawer, { props: { modelValue: true, side: 'left' } })

    expect(body().find('.left-0').exists()).toBe(true)
    expect(body().find('.right-0').exists()).toBe(false)
  })

  it('emits update:modelValue false when the close button is clicked', async () => {
    wrapper = mount(BaseDrawer, { props: { modelValue: true } })

    await body().find('[aria-label="Close"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('emits update:modelValue false when Escape is pressed while open', async () => {
    wrapper = mount(BaseDrawer, { props: { modelValue: true } })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })
})
