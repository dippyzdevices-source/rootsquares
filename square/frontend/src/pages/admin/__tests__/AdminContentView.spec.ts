// Tests for AdminContentView (5 cases), e.g. AdminContentView; shows the Site group by default, with its sub-sections; puts Header & footer under Site, and Home page and Legal texts under P.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AdminContentView from '../AdminContentView.vue'

// useSettingsGroup reads $route from the app's globalProperties
const onHub = (group: string) => ({ install: (app: { config: { globalProperties: Record<string, unknown> } }) => { app.config.globalProperties.$route = { path: '/admin/content', query: { group } } } })
const stubs = { RouterLink: { template: '<a :to="to"><slot /></a>', props: ['to'] } }

describe('AdminContentView', () => {
  it('shows the Site group by default, with its sub-sections', () => {
    const wrapper = mount(AdminContentView, { global: { stubs } })

    expect(wrapper.find('h1').text()).toBe('Settings')
    expect(wrapper.findAll('section.settings-group').map((g) => g.find('h2').text())).toEqual(['Site'])
    expect(wrapper.text()).toContain('Site availability')
    expect(wrapper.text()).toContain('Contact details')
    expect(wrapper.find('a[to="/admin/content/contact-details"]').exists()).toBe(true)
    expect(wrapper.find('a[to="/admin/content/settings"]').exists()).toBe(true)
    expect(wrapper.find('a[to="/admin/content/committee"]').exists()).toBe(false)
  })
  it('puts Header & footer under Site, and Home page and Legal texts under Pages & media (W6-R74)', () => {
    const site = mount(AdminContentView, { global: { stubs } })
    expect(site.find('a[to="/admin/content/header-footer"]').exists()).toBe(true)
    expect(site.find('a[to="/admin/content/home"]').exists()).toBe(false)
    expect(site.find('a[to="/admin/content/legal-texts"]').exists()).toBe(false)
  })
  it('has one card per public page under Pages & media (W8-R4)', () => {
    const wrapper = mount(AdminContentView, { global: { stubs, plugins: [onHub('pages')] } })
    const links = wrapper.findAll('a.ds-card').map((a) => a.attributes('to'))
    expect(links).toEqual(['/admin/content/home', '/admin/content/pages/events', '/admin/content/pages/gallery', '/admin/content/pages/news', '/admin/content/pages/newsletter', '/admin/content/pages/membership', '/admin/content/pages/contact', '/admin/content/pages/committee', '/admin/content/pages/about', '/admin/content/legal-texts'])
  })
  it('has Sponsors under People, next to Committee and Founders (W8-R4)', () => {
    const wrapper = mount(AdminContentView, { global: { stubs, plugins: [onHub('people')] } })
    expect(wrapper.findAll('a.ds-card').map((a) => a.attributes('to'))).toEqual(['/admin/content/committee', '/admin/content/founders', '/admin/content/sponsors'])
  })
})
