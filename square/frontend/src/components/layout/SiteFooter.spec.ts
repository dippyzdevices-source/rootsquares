// Tests for SiteFooter (3 cases), e.g. SiteFooter: the square's own words (W6-R70); shows only what the square set: nothing extra by default, the year and; shows the registration line, description, copyright line and the socia.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockLoadHomeContent = vi.fn()

vi.mock('../../services/siteContent', async () => {
  const actual = await vi.importActual<typeof import('../../services/siteContent')>('../../services/siteContent')
  return { ...actual, loadHomeContent: () => mockLoadHomeContent() }
})
vi.mock('../../services/settingsApi', () => ({ fetchSettings: () => Promise.resolve({ contact_email: 'hello@club.example' }) }))

import SiteFooter from './SiteFooter.vue'
import { EMPTY_HOME_CONTENT } from '../../services/siteContent'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => vi.clearAllMocks())

describe("SiteFooter: the square's own words (W6-R70)", () => {
  it('shows only what the square set: nothing extra by default, the year and name as copyright', async () => {
    mockLoadHomeContent.mockResolvedValue({ ...EMPTY_HOME_CONTENT })
    const wrapper = mount(SiteFooter, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Follow us')
    expect(wrapper.find('.ds-footer-blurb').exists()).toBe(false)
    expect(wrapper.text()).toContain(`© ${new Date().getFullYear()}`)
    expect(wrapper.text()).toContain('hello@club.example')
  })

  it('shows the registration line, description, copyright line and the social icons it has set', async () => {
    mockLoadHomeContent.mockResolvedValue({
      ...EMPTY_HOME_CONTENT,
      footer_registration: 'Org. nr. 995757664',
      footer_blurb: 'A cultural association.',
      footer_copyright: 'Our own copyright line',
      social_links: [
        { network: 'facebook', url: 'https://www.facebook.com/bcaoslo' },
        { network: 'youtube', url: 'https://youtube.com/@bca' },
      ],
    })
    const wrapper = mount(SiteFooter, { global: { stubs } })
    await flushPromises()
    const text = wrapper.text()
    for (const part of ['Org. nr. 995757664', 'A cultural association.', 'Our own copyright line', 'Follow us']) expect(text).toContain(part)
    const links = wrapper.findAll('a.footer-social')
    expect(links.map((l) => l.attributes('href'))).toEqual(['https://www.facebook.com/bcaoslo', 'https://youtube.com/@bca'])
    expect(links[0]!.attributes('rel')).toBe('noopener noreferrer')
    expect(text).not.toContain(`© ${new Date().getFullYear()}`)
  })
})
