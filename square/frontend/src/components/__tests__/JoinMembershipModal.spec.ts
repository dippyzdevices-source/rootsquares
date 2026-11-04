// Tests for JoinMembershipModal (5 cases), e.g. JoinMembershipModal; offers the available payment methods and blocks an empty submit; shows the convenience fee and the total for the selected method.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockOptions = vi.fn()
const mockJoin = vi.fn()

vi.mock('../../services/membershipJoinApi', () => ({
  fetchJoinOptions: (...a: unknown[]) => mockOptions(...a),
  joinMembership: (...a: unknown[]) => mockJoin(...a),
}))

import JoinMembershipModal from '../JoinMembershipModal.vue'

const adult = { name: 'adult', price: 300, billing_frequency: 'yearly' as const, contact_for_price: false }
const child = { name: 'child', price: 100, billing_frequency: 'yearly' as const, contact_for_price: false }
const stubs = { RouterLink: { template: '<a><slot /></a>' } }

let wrapper: ReturnType<typeof mount>
const body = () => new DOMWrapper(document.body)

async function open(type: typeof adult) {
  wrapper = mount(JoinMembershipModal, { props: { modelValue: false, type }, global: { stubs } })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
}

async function fill(name: string, email: string) {
  const inputs = body().findAll('input:not([type=radio])')
  await inputs[0].setValue(name)
  await inputs[1].setValue(email)
}

beforeEach(() => {
  vi.clearAllMocks()
  mockOptions.mockResolvedValue({
    payment_methods: ['vipps_app', 'vipps_qr', 'pay_later'],
    convenience_percent: { vipps_app: 5, vipps_qr: 0 },
  })
})
afterEach(() => wrapper.unmount())

describe('JoinMembershipModal', () => {
  it('offers the available payment methods and blocks an empty submit', async () => {
    await open(adult)
    expect(body().text()).toContain('Pay in the Vipps app')
    expect(body().text()).toContain('Pay with Vipps QR')
    expect(body().text()).toContain('Pay later')

    await body().find('form').trigger('submit')
    expect(mockJoin).not.toHaveBeenCalled()
    expect(body().text()).toContain('This field is required.')
  })

  it('shows the convenience fee and the total for the selected method', async () => {
    await open(adult)
    expect(body().text()).toContain('+ 15.00 kr convenience fee')
    expect(body().find('[data-testid=join-total]').text()).toContain('315.00 kr')
    await body().findAll('input[type=radio]')[1].setValue(true)
    expect(body().find('[data-testid=join-total]').exists()).toBe(false)
  })

  it('sends the chosen method and shows the confirmation for Vipps QR', async () => {
    mockJoin.mockResolvedValue({
      membership_type: 'adult',
      payment_method: 'vipps_qr',
      payment: { id: 1, payment_reference: 'PAY-1', amount: 30000, status: 'pending' },
      redirect_url: null,
    })
    await open(adult)
    await fill('Priya Das', 'priya@example.com')
    await body().findAll('input[type=radio]')[1].setValue(true)
    await body().find('form').trigger('submit')
    await flushPromises()

    expect(mockJoin).toHaveBeenCalledWith(
      expect.objectContaining({ membership_type: 'adult', email: 'priya@example.com', payment_method: 'vipps_qr' }),
    )
    expect(body().text()).toContain('as soon as we confirm your payment')
  })

  it('sends a child signup with the parent email', async () => {
    mockJoin.mockResolvedValue({ membership_type: 'child', payment_method: 'pay_later', payment: null, redirect_url: null })
    await open(child)
    await fill('Kid', 'parent@example.com')
    await body().find('form').trigger('submit')
    await flushPromises()

    const payload = mockJoin.mock.calls[0][0]
    expect(payload.parent_email).toBe('parent@example.com')
    expect(payload.email).toBeUndefined()
  })
})
