// Tests for SettingsSectionNav (2 cases), e.g. SettingsSectionNav; shows only the high-level groups as tabs.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SettingsSectionNav from '../SettingsSectionNav.vue'

const RouterLinkStub = { props: ['to'], template: '<a><slot /></a>' }

describe('SettingsSectionNav', () => {
  it('shows only the high-level groups as tabs', () => {
    const wrapper = mount(SettingsSectionNav, { global: { stubs: { 'router-link': RouterLinkStub } } })
    expect(wrapper.findAll('a').map((a) => a.text())).toEqual(['Site', 'People', 'Pages & media', 'Lists'])
    expect(wrapper.findAll('a')[0].classes()).toContain('ds-tab-active')
  })
})
