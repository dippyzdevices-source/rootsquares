// Tests for CommitteeOff (3 cases), e.g. the public site and the Committee module; on: the footer and the About page link to the committee; off: no Organisation block in the footer and no committee button on th.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Committee module (W8-R12): no link to the committee page anywhere on the public site.
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => !off.keys.includes(key ?? '') }))
vi.mock('../../../services/settingsApi', () => ({ fetchSettings: () => Promise.resolve({ contact_email: 'hello@club.example', heritage_image_url: null }) }))
vi.mock('../../../services/foundersApi', () => ({ fetchFounders: () => Promise.resolve([]) }))
const mockHomeContent = vi.fn()
vi.mock('../../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/siteContent')>()),
  loadHomeContent: () => mockHomeContent(),
}))

import { EMPTY_ABOUT_PAGE, fillHomeContent } from '../../../services/siteContent'
import SiteFooter from '../../../components/layout/SiteFooter.vue'
import HeritageView from '../HeritageView.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
  off.keys = []
  mockHomeContent.mockResolvedValue(fillHomeContent({ about_page: { ...EMPTY_ABOUT_PAGE, values_title: 'Who we are', values_button: 'Meet the committee', values: [{ title: 'Community', description: 'First' }] } }))
})

describe('the public site and the Committee module', () => {
  it('on: the footer and the About page link to the committee', async () => {
    const footer = mount(SiteFooter, { global: { stubs } })
    const about = mount(HeritageView, { global: { stubs } })
    await flushPromises()
    expect(footer.find('a[href="/committee"]').exists()).toBe(true)
    expect(about.find('a[href="/committee"]').exists()).toBe(true)
  })

  it('off: no Organisation block in the footer and no committee button on the About page', async () => {
    off.keys = ['committee']
    const footer = mount(SiteFooter, { global: { stubs } })
    const about = mount(HeritageView, { global: { stubs } })
    await flushPromises()
    expect(footer.find('a[href="/committee"]').exists()).toBe(false)
    expect(footer.text()).not.toContain('Organisation')
    expect(about.find('a[href="/committee"]').exists()).toBe(false)
    expect(about.text()).toContain('Who we are')
  })
})
