// Tests for SleepingView (5 cases), e.g. SleepingView; says the square is resting and shows the contact details it has; shows no contact block when the platform copied none.
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// The back-soon page of a sleeping square (W17-R24): the square's name and the contact details the platform copied; nothing of the maintenance page.
const profile = vi.hoisted(() => ({ name: 'Neon Test', sleepContact: { email: 'hello@example.org', phone: '+47 400 00 000', address: '' } }))
vi.mock('../../../services/squareConfig', () => ({ squareProfile: profile }))

import SleepingView from '../SleepingView.vue'
import UnderConstructionView from '../UnderConstructionView.vue'

describe('SleepingView', () => {
  it('says the square is resting and shows the contact details it has', () => {
    const wrapper = mount(SleepingView)
    expect(wrapper.find('h1').text()).toBe('Neon Test is taking a rest')
    expect(wrapper.find('[data-testid="sleeping-page"]').element.tagName).toBe('MAIN')
    const contact = wrapper.find('[data-testid="resting-contact"]')
    expect(contact.find('a[href="mailto:hello@example.org"]').exists()).toBe(true)
    expect(contact.find('a[href="tel:+4740000000"]').exists()).toBe(true)
    expect(contact.text()).not.toContain('undefined')
  })

  it('shows no contact block when the platform copied none', () => {
    profile.sleepContact = { email: '', phone: '', address: '' }
    const wrapper = mount(SleepingView)
    expect(wrapper.find('[data-testid="resting-contact"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('You can still reach us')
  })
})

describe('UnderConstructionView', () => {
  it('is only the maintenance page: no resting message, links to what is ready', () => {
    const wrapper = mount(UnderConstructionView, { global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } } })
    expect(wrapper.text()).toContain('This page is under construction')
    expect(wrapper.text()).not.toContain('taking a rest')
  })
})
