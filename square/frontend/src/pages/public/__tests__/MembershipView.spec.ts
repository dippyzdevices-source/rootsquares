// Tests for MembershipView (9 cases), e.g. MembershipView; prompts a signed-out visitor to create an account; links an authenticated visitor straight to their dashboard.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../../stores/auth'

const mockFetchMembershipTypes = vi.fn()

vi.mock('../../../services/memberApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/memberApi')>(
    '../../../services/memberApi',
  )
  return {
    ...actual,
    fetchMembershipTypes: (...args: unknown[]) => mockFetchMembershipTypes(...args),
  }
})

const mockHomeContent = vi.fn()
vi.mock('../../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/siteContent')>()),
  loadHomeContent: () => mockHomeContent(),
}))

import { fillHomeContent } from '../../../services/siteContent'
import MembershipView from '../MembershipView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  mockHomeContent.mockResolvedValue(fillHomeContent(undefined))
  mockFetchMembershipTypes.mockResolvedValue([
    { name: 'individual', price: 500, billing_frequency: 'yearly', contact_for_price: false },
    { name: 'family', price: 800, billing_frequency: 'yearly', contact_for_price: false },
    { name: 'student', price: 250, billing_frequency: 'monthly', contact_for_price: false },
    { name: 'senior', price: 250, billing_frequency: 'quarterly', contact_for_price: false },
    { name: 'lifetime', price: null, billing_frequency: 'yearly', contact_for_price: true },
  ])
})

describe('MembershipView', () => {
  it('prompts a signed-out visitor to create an account', async () => {
    const wrapper = mount(MembershipView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Create an account')
    expect(wrapper.text()).not.toContain('Go to my dashboard')
  })

  it('links an authenticated visitor straight to their dashboard', async () => {
    const auth = useAuthStore()
    auth.session = { access_token: 'token-123' } as never

    const wrapper = mount(MembershipView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Go to my dashboard')
    expect(wrapper.text()).not.toContain('Create an account')
  })

  it('lists every membership type with its real price and billing frequency', async () => {
    const wrapper = mount(MembershipView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Individual')
    expect(wrapper.text()).toContain('Family')
    expect(wrapper.text()).toContain('Student')
    expect(wrapper.text()).toContain('Senior')
    expect(wrapper.text()).toContain('Lifetime')
    expect(wrapper.text()).toContain('500 kr / year')
    expect(wrapper.text()).toContain('250 kr / month')
    expect(wrapper.text()).toContain('250 kr / quarter')
  })

  it('shows a Contact link instead of a price for a contact-for-price type', async () => {
    const wrapper = mount(MembershipView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Contact us for pricing')
    expect(wrapper.find('a[to="/contact"]').exists()).toBe(true)
  })

  it('shows no why-join or how-to-join list until the square writes them (W7-R11)', async () => {
    const wrapper = mount(MembershipView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('ul').exists()).toBe(false)
    expect(wrapper.find('ol').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Why join')
    expect(wrapper.text()).not.toContain('vote at general meetings')
    expect(wrapper.text()).toContain('Create an account') // the join buttons stay
  })

  it("shows the square's own reasons and steps, each list only when it has lines", async () => {
    mockHomeContent.mockResolvedValue(
      fillHomeContent({
        membership_page: { benefits_eyebrow: 'Why join', benefits: [{ text: 'Cheaper tickets' }], steps_eyebrow: '', steps: [] },
      }),
    )
    const wrapper = mount(MembershipView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Why join')
    expect(wrapper.findAll('ul li')).toHaveLength(1)
    expect(wrapper.text()).toContain('Cheaper tickets')
    expect(wrapper.find('ol').exists()).toBe(false)
  })
})

describe('MembershipView join form', () => {
  it('opens the join form for the tapped type and keeps the buttons below the table', async () => {
    const wrapper = mount(MembershipView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('tr[data-type="family"]').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Join as Family')

    const html = wrapper.html()
    expect(html.indexOf('Create an account')).toBeGreaterThan(html.indexOf('</table>'))
    expect(html.indexOf('Why join')).toBeLessThan(html.indexOf('Membership types'))
    wrapper.unmount()
  })
})
