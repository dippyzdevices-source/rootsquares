// Tests for AdminHeaderFooterView (5 cases), e.g. AdminHeaderFooterView (W6-R74); shows the header and footer words, the choices and the social links, a; saves its own words and keeps the home page words as they are now.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminSettings = vi.fn()
const mockUpdateAdminSettings = vi.fn()

vi.mock('../../../services/adminSettingsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminSettingsApi')>('../../../services/adminSettingsApi')
  return {
    ...actual,
    fetchAdminSettings: (...args: unknown[]) => mockFetchAdminSettings(...args),
    updateAdminSettings: (...args: unknown[]) => mockUpdateAdminSettings(...args),
  }
})
vi.mock('../../../composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }))

import AdminHeaderFooterView from '../AdminHeaderFooterView.vue'
import AdminHomeContentView from '../AdminHomeContentView.vue'

const stubs = { SettingsSectionNav: true, RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }
const saveButton = (wrapper: ReturnType<typeof mount>) => wrapper.findAll('button').find((b) => b.text() === 'Save')!

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminSettings.mockResolvedValue({
    home_content: { headline: 'Hello', utility_text: 'Oslo · est. 2010', footer_blurb: 'About us', logo_size: 'large', social_links: [{ network: 'facebook', url: 'https://www.facebook.com/x' }] },
  })
  mockUpdateAdminSettings.mockImplementation(async (payload: { home_content: object }) => ({ home_content: payload.home_content }))
})

describe('AdminHeaderFooterView (W6-R74)', () => {
  it('shows the header and footer words, the choices and the social links, and nothing of the home page', async () => {
    const wrapper = mount(AdminHeaderFooterView, { global: { stubs } })
    await flushPromises()
    expect((wrapper.get('input[aria-label="Top bar text"]').element as HTMLInputElement).value).toBe('Oslo · est. 2010')
    expect(wrapper.findAll('.base-select-value')[0].text()).toBe('Large')
    expect((wrapper.get('input[aria-label="facebook address"]').element as HTMLInputElement).value).toBe('https://www.facebook.com/x')
    expect(wrapper.find('input[aria-label="Headline"]').exists()).toBe(false)
  })

  it('saves its own words and keeps the home page words as they are now', async () => {
    const wrapper = mount(AdminHeaderFooterView, { global: { stubs } })
    await flushPromises()
    await wrapper.get('input[aria-label="Top bar text"]').setValue('New top bar')
    await saveButton(wrapper).trigger('click')
    await flushPromises()
    const sent = (mockUpdateAdminSettings.mock.calls[0][0] as { home_content: Record<string, unknown> }).home_content
    expect(sent.utility_text).toBe('New top bar')
    expect(sent.headline).toBe('Hello') // the home page's words, fetched just before saving, are kept
    expect(sent.social_links).toEqual([{ network: 'facebook', url: 'https://www.facebook.com/x' }])
  })
})

describe('AdminHomeContentView keeps the header and footer words (W6-R74)', () => {
  it('saving the home page does not touch the top bar, footer or social links', async () => {
    const wrapper = mount(AdminHomeContentView, { global: { stubs } })
    await flushPromises()
    await wrapper.get('input[aria-label="Headline"]').setValue('Changed headline')
    await saveButton(wrapper).trigger('click')
    await flushPromises()
    const sent = (mockUpdateAdminSettings.mock.calls[0][0] as { home_content: Record<string, unknown> }).home_content
    expect(sent.headline).toBe('Changed headline')
    expect(sent.utility_text).toBe('Oslo · est. 2010')
    expect(sent.footer_blurb).toBe('About us')
    expect(sent.logo_size).toBe('large')
    expect(sent.social_links).toEqual([{ network: 'facebook', url: 'https://www.facebook.com/x' }])
  })
})
