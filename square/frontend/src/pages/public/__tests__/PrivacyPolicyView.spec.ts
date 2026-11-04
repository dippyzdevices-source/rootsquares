// Tests for PrivacyPolicyView (3 cases), e.g. shows the square's own text when it has published one (W6-R51); says the square has not published it yet and shows the square's own co; carries nothing of bca-oslo (name, organisation number, address, Norwe.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchSettings = vi.fn()
vi.mock('../../../services/settingsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/settingsApi')>('../../../services/settingsApi')
  return { ...actual, fetchSettings: (...args: unknown[]) => mockFetchSettings(...args) }
})

import PrivacyPolicyView from '../PrivacyPolicyView.vue'
import TermsOfSaleView from '../TermsOfSaleView.vue'

beforeEach(() => vi.clearAllMocks())

// bca-oslo's own legal texts named its legal entity, organisation number, address and Norwegian law, so they were removed (rootsquares W6-R41).
describe.each([
  ['Privacy Policy', PrivacyPolicyView, 'privacy policy', 'privacy_text'],
  ['Terms of Sale', TermsOfSaleView, 'terms of sale', 'terms_text'],
])('%s', (title, component, what, field) => {
  it("shows the square's own text when it has published one (W6-R51)", async () => {
    mockFetchSettings.mockResolvedValue({ contact_email: 'hello@club.example', [field]: 'Our own text. Second line.' })
    const wrapper = mount(component)
    await flushPromises()
    expect(wrapper.get('[data-testid=legal-text]').text()).toContain('Our own text.')
    expect(wrapper.text()).not.toContain('has not published')
  })


  it("says the square has not published it yet and shows the square's own contact details", async () => {
    mockFetchSettings.mockResolvedValue({ contact_email: 'hello@club.example', contact_phone: '+1 555 0100', contact_address: '1 Main Street' })
    const wrapper = mount(component)
    await flushPromises()
    expect(wrapper.text()).toContain(title)
    expect(wrapper.text()).toContain(`has not published its ${what}`)
    expect(wrapper.text()).toContain('hello@club.example')
    expect(wrapper.text()).toContain('1 Main Street')
  })

  it('carries nothing of bca-oslo (name, organisation number, address, Norwegian law)', async () => {
    mockFetchSettings.mockRejectedValue(new Error('offline'))
    const wrapper = mount(component)
    await flushPromises()
    for (const word of ['995757664', 'Niladri', 'Bølerlia', 'Norwegian', 'NOK', 'Bengali']) expect(wrapper.text()).not.toContain(word)
    expect(wrapper.text()).toContain(`has not published its ${what}`) // still useful without the settings
  })
})
