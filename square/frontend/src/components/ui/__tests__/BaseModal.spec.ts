// Tests for BaseModal (10 cases), e.g. BaseModal; does not render when modelValue is false; renders the title and slot content when modelValue is true.
import { describe, it, expect, afterEach } from 'vitest'
import { DOMWrapper, mount, type VueWrapper } from '@vue/test-utils'
import BaseModal from '../BaseModal.vue'

// BaseModal renders via <Teleport to="body">, so its content lives outside the
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

describe('BaseModal', () => {
  it('does not render when modelValue is false', () => {
    wrapper = mount(BaseModal, { props: { modelValue: false } })

    expect(body().find('[role="dialog"]').exists()).toBe(false)
  })

  it('renders the title and slot content when modelValue is true', () => {
    wrapper = mount(BaseModal, {
      props: { modelValue: true, title: 'Confirm' },
      slots: { default: 'Are you sure?' },
    })

    expect(body().find('[role="dialog"]').exists()).toBe(true)
    expect(body().text()).toContain('Confirm')
    expect(body().text()).toContain('Are you sure?')
  })

  it('skips the header band entirely when no title is given, using a floating close button instead', () => {
    wrapper = mount(BaseModal, {
      props: { modelValue: true },
      slots: { default: '<img alt="photo" />' },
    })

    expect(body().find('.ds-modal-head').exists()).toBe(false)
    expect(body().find('.ds-modal-close-floating').exists()).toBe(true)
    expect(body().find('[aria-label="Close"]').exists()).toBe(true)
  })

  it('gets a tighter-padding class when title-less (a photo/receipt viewer), not when titled', () => {
    wrapper = mount(BaseModal, { props: { modelValue: true } })
    expect(body().find('[role="dialog"]').classes()).toContain('ds-modal-untitled')
    wrapper.unmount()

    wrapper = mount(BaseModal, { props: { modelValue: true, title: 'Confirm' } })
    expect(body().find('[role="dialog"]').classes()).not.toContain('ds-modal-untitled')
  })

  it('gets a shrink-to-fit class only when hugContent is passed', () => {
    wrapper = mount(BaseModal, { props: { modelValue: true } })
    expect(body().find('[role="dialog"]').classes()).not.toContain('ds-modal-hug')
    wrapper.unmount()

    wrapper = mount(BaseModal, { props: { modelValue: true, hugContent: true } })
    expect(body().find('[role="dialog"]').classes()).toContain('ds-modal-hug')
  })

  it('falls back to an aria-label on the dialog when title-less, for accessibility', () => {
    wrapper = mount(BaseModal, {
      props: { modelValue: true, ariaLabel: 'Photo preview' },
    })

    expect(body().find('[role="dialog"]').attributes('aria-label')).toBe('Photo preview')
  })

  it('emits update:modelValue false when the close button is clicked', async () => {
    wrapper = mount(BaseModal, { props: { modelValue: true } })

    await body().find('[aria-label="Close"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('emits update:modelValue false when Escape is pressed while open', async () => {
    wrapper = mount(BaseModal, { props: { modelValue: true } })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('does not react to Escape when already closed', async () => {
    wrapper = mount(BaseModal, { props: { modelValue: false } })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
