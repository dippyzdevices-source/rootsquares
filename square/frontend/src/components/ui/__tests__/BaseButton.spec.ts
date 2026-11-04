// Tests for BaseButton (8 cases), e.g. BaseButton; defaults to the primary variant and md size, rendering a <button>; applies the requested variant and size classes.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseButton from '../BaseButton.vue'

// Matches the stub pattern used across this codebase's other specs (e.g. HeritageView.spec.ts)
// rather than mounting a real router — a real RouterLink needs the router "installed" via
// app.use for its href resolution to render synchronously in jsdom.
const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

describe('BaseButton', () => {
  it('defaults to the primary variant and md size, rendering a <button>', () => {
    const wrapper = mount(BaseButton, { slots: { default: 'Save' } })

    expect(wrapper.classes()).toContain('ds-btn')
    expect(wrapper.classes()).toContain('ds-btn-primary')
    expect(wrapper.classes()).toContain('ds-btn-md')
    expect(wrapper.element.tagName).toBe('BUTTON')
  })

  it('applies the requested variant and size classes', () => {
    const wrapper = mount(BaseButton, { props: { variant: 'secondary', size: 'lg' } })

    expect(wrapper.classes()).toContain('ds-btn-secondary')
    expect(wrapper.classes()).toContain('ds-btn-lg')
    expect(wrapper.classes()).not.toContain('ds-btn-primary')
  })

  it('defaults the native button type to "button" and respects an override', () => {
    const wrapper = mount(BaseButton)
    expect(wrapper.attributes('type')).toBe('button')

    const submitWrapper = mount(BaseButton, { props: { type: 'submit' } })
    expect(submitWrapper.attributes('type')).toBe('submit')
  })

  it('renders as a RouterLink when `to` is given', () => {
    const wrapper = mount(BaseButton, { props: { to: '/membership' }, global: { stubs } })

    expect(wrapper.attributes('href')).toBe('/membership')
    expect(wrapper.attributes('type')).toBeUndefined()
  })

  it('renders as an <a> when `href` is given', () => {
    const wrapper = mount(BaseButton, { props: { href: 'https://example.com' } })

    expect(wrapper.element.tagName).toBe('A')
    expect(wrapper.attributes('href')).toBe('https://example.com')
  })

  it('adds ds-btn-full when fullWidth is set', () => {
    const wrapper = mount(BaseButton, { props: { fullWidth: true } })

    expect(wrapper.classes()).toContain('ds-btn-full')
  })

  it('disables a native button and marks a link variant aria-disabled instead', () => {
    const buttonWrapper = mount(BaseButton, { props: { disabled: true } })
    expect(buttonWrapper.attributes('disabled')).toBeDefined()

    const linkWrapper = mount(BaseButton, { props: { href: '#', disabled: true } })
    expect(linkWrapper.attributes('aria-disabled')).toBe('true')
    expect(linkWrapper.attributes('tabindex')).toBe('-1')
  })
})
