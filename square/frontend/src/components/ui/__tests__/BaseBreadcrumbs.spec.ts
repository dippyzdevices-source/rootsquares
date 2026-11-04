// Tests for BaseBreadcrumbs (3 cases), e.g. BaseBreadcrumbs; links every item but the last, which is the current page; shows the home item as an icon and offers the parent as a back link.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseBreadcrumbs from '../BaseBreadcrumbs.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }
const items = [{ label: 'Home', to: '/' }, { label: 'Events', to: '/events' }, { label: 'Mahalaya 2026' }]

describe('BaseBreadcrumbs', () => {
  it('links every item but the last, which is the current page', () => {
    const wrapper = mount(BaseBreadcrumbs, { props: { items }, global: { stubs } })

    expect(wrapper.find('nav').attributes('aria-label')).toBe('Breadcrumb')
    const trailLinks = wrapper.findAll('ol a').map((a) => a.attributes('href'))
    expect(trailLinks).toEqual(['/', '/events'])
    expect(wrapper.find('[aria-current="page"]').text()).toBe('Mahalaya 2026')
    expect(wrapper.findAll('li')).toHaveLength(3)
  })

  it('shows the home item as an icon and offers the parent as a back link', () => {
    const wrapper = mount(BaseBreadcrumbs, { props: { items }, global: { stubs } })

    const home = wrapper.find('ol a[href="/"]')
    expect(home.attributes('aria-label')).toBe('Home')
    expect(home.text()).toBe('')
    expect(home.find('svg').exists()).toBe(true)

    const back = wrapper.find('a.ds-breadcrumbs-back')
    expect(back.attributes('href')).toBe('/events')
    expect(back.text()).toBe('Events')
  })
})
