// Tests for GettingStartedCard (3 cases), e.g. GettingStartedCard; lists where to begin with a link for each step; can be closed, and stays closed.
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import GettingStartedCard from '../GettingStartedCard.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

describe('GettingStartedCard', () => {
  beforeEach(() => localStorage.clear())

  it('lists where to begin with a link for each step', () => {
    const wrapper = mount(GettingStartedCard, { global: { stubs } })
    expect(wrapper.text()).toContain('Where to begin')
    const links = wrapper.findAll('a').map((a) => a.attributes('href'))
    expect(links).toContain('/admin/content/payments')
    expect(links).toContain('/admin/events/new')
    expect(links).toContain('/admin/donations')
    expect(links).toContain('/admin/messages/reminders')
  })

  it('can be closed, and stays closed', async () => {
    const wrapper = mount(GettingStartedCard, { global: { stubs } })
    await wrapper.find('.close-getting-started').trigger('click')
    expect(wrapper.find('.getting-started').exists()).toBe(false)
    expect(mount(GettingStartedCard, { global: { stubs } }).find('.getting-started').exists()).toBe(false)
  })
})
