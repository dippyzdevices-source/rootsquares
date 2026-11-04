// Tests for MembershipDriveView (11 cases), e.g. MembershipDriveView; shows membership types with descriptions, ready to tap-select; moves to the details form after selecting a type.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchMembershipTypes = vi.fn()
const mockSignup = vi.fn()
const mockOptions = vi.fn()
const mockSettings = vi.fn()

vi.mock('../../../services/memberApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/memberApi')>(
    '../../../services/memberApi',
  )
  return { ...actual, fetchMembershipTypes: (...args: unknown[]) => mockFetchMembershipTypes(...args) }
})

vi.mock('../../../services/membershipDriveApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/membershipDriveApi')>(
    '../../../services/membershipDriveApi',
  )
  return {
    ...actual,
    signupMembershipDrive: (...args: unknown[]) => mockSignup(...args),
    fetchDriveOptions: (...args: unknown[]) => mockOptions(...args),
  }
})

vi.mock('../../../services/settingsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/settingsApi')>('../../../services/settingsApi')
  return { ...actual, fetchSettings: (...args: unknown[]) => mockSettings(...args) }
})

import MembershipDriveView from '../MembershipDriveView.vue'
import { ValidationError } from '../../../services/membershipDriveApi'

const types = [
  { name: 'Individual', price: 300, billing_frequency: 'yearly', contact_for_price: false, description: 'For one adult member of the community.' },
  { name: 'Lifetime', price: null, billing_frequency: 'yearly', contact_for_price: true },
]

beforeEach(() => {
  vi.clearAllMocks()
  mockOptions.mockResolvedValue({ cash_enabled: false })
  mockSettings.mockResolvedValue({ vipps_number: '24680' }) // the square's own Vipps number (W6-R38)
})

async function selectTypeAt(wrapper: ReturnType<typeof mount>, i: number) {
  await wrapper.findAll('button.ds-card')[i].trigger('click')
}

describe('MembershipDriveView', () => {
  it('shows membership types with descriptions, ready to tap-select', async () => {
    mockFetchMembershipTypes.mockResolvedValue(types)

    const wrapper = mount(MembershipDriveView)
    await flushPromises()

    expect(wrapper.text()).toContain('Individual')
    expect(wrapper.text()).toContain('300 kr / year')
    expect(wrapper.text()).toContain('Lifetime')
    expect(wrapper.text()).toContain('For one adult member of the community.')
  })

  it('moves to the details form after selecting a type', async () => {
    mockFetchMembershipTypes.mockResolvedValue(types)

    const wrapper = mount(MembershipDriveView)
    await flushPromises()

    await selectTypeAt(wrapper, 0)

    expect(wrapper.find('input[type="email"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Continue to payment')
  })

  it('blocks continuing and shows errors when required fields are empty', async () => {
    mockFetchMembershipTypes.mockResolvedValue(types)

    const wrapper = mount(MembershipDriveView)
    await flushPromises()
    await selectTypeAt(wrapper, 0)

    await wrapper.find('input[type="email"]').setValue('')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('This field is required.')
    // Still on the details form, not the Vipps QR step.
    expect(wrapper.find('input[type="email"]').exists()).toBe(true)
  })

  it('shows the Vipps QR before ever calling the signup API, and only submits once payment is confirmed', async () => {
    mockFetchMembershipTypes.mockResolvedValue(types)
    mockSignup.mockResolvedValue({
      member: { id: 1, name: 'Priya Das', email: 'priya@example.com' },
      membership: { id: 1, membership_type: 'Individual', status: 'active', start_date: '2026-09-28', end_date: null },
      payment: { id: 1, amount: 30000, currency: 'NOK', status: 'paid' },
    })

    const wrapper = mount(MembershipDriveView)
    await flushPromises()
    await selectTypeAt(wrapper, 0)

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('Priya Das')
    await inputs[1].setValue('priya@example.com')
    await inputs[2].setValue('41234567')
    await wrapper.find('form').trigger('submit.prevent')

    // The QR step is shown, and nothing has been submitted to the backend yet.
    expect(mockSignup).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Pay with Vipps')
    expect(wrapper.find('img[alt="Vipps payment QR code"]').exists()).toBe(false) // no QR image: bca-oslo's would have paid BCA
    expect(wrapper.text()).toContain('24680')
    expect(wrapper.text()).toContain('Priya Das')

    await wrapper.find('button.ds-btn-primary').trigger('click')
    await flushPromises()

    expect(mockSignup).toHaveBeenCalledWith({
      name: 'Priya Das',
      email: 'priya@example.com',
      phone: '41234567',
      membership_type: 'Individual',
      payment_method: 'vipps_qr',
    })
    expect(wrapper.text()).toContain('is now active')
    expect(wrapper.text()).toContain('300 kr')
    expect(wrapper.text()).toContain('Sign up another member')
  })

  it('shows field-level errors returned by the backend after confirming payment', async () => {
    mockFetchMembershipTypes.mockResolvedValue(types)
    mockSignup.mockRejectedValue(new ValidationError({ email: 'Enter a valid email address.' }))

    const wrapper = mount(MembershipDriveView)
    await flushPromises()
    await selectTypeAt(wrapper, 0)

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('Priya Das')
    await inputs[1].setValue('priya@example.com')
    await inputs[2].setValue('41234567')
    await wrapper.find('form').trigger('submit.prevent')
    await wrapper.find('button.ds-btn-primary').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Enter a valid email address.')
  })

  it('skips the Vipps QR step entirely for a contact-for-price type', async () => {
    mockFetchMembershipTypes.mockResolvedValue(types)
    mockSignup.mockResolvedValue({
      member: { id: 2, name: 'Rupa Sengupta', email: 'rupa@example.com' },
      membership: { id: 2, membership_type: 'Lifetime', status: 'active', start_date: '2026-09-28', end_date: null },
      payment: null,
    })

    const wrapper = mount(MembershipDriveView)
    await flushPromises()
    await selectTypeAt(wrapper, 1)

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('Rupa Sengupta')
    await inputs[1].setValue('rupa@example.com')
    await inputs[2].setValue('41234567')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(mockSignup).toHaveBeenCalledWith({
      name: 'Rupa Sengupta',
      email: 'rupa@example.com',
      phone: '41234567',
      membership_type: 'Lifetime',
    })
    expect(wrapper.text()).not.toContain('Pay with Vipps')
    expect(wrapper.text()).toContain('is now active')
  })

  it('offers Cash next to Vipps-QR only while an admin has it switched on, and sends the chosen method', async () => {
    mockFetchMembershipTypes.mockResolvedValue(types)
    mockOptions.mockResolvedValue({ cash_enabled: true })
    mockSignup.mockResolvedValue({
      member: { id: 1, name: 'Priya Das', email: 'priya@example.com' },
      membership: { id: 1, membership_type: 'Individual', status: 'active', start_date: '2026-09-28', end_date: null },
      payment: { id: 1, amount: 30000, currency: 'NOK', status: 'paid' },
    })

    const wrapper = mount(MembershipDriveView)
    await flushPromises()
    await selectTypeAt(wrapper, 0)
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('Priya Das')
    await inputs[1].setValue('priya@example.com')
    await inputs[2].setValue('41234567')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.find('.drive-methods').exists()).toBe(true)
    await wrapper.find('input[name="drive-pay"][value="cash"]').setValue(true)
    expect(wrapper.find('.drive-cash').text()).toContain('in cash')
    expect(wrapper.find('img[alt="Vipps payment QR code"]').exists()).toBe(false)

    await wrapper.find('button.ds-btn-primary').trigger('click')
    await flushPromises()
    expect(mockSignup).toHaveBeenCalledWith(expect.objectContaining({ payment_method: 'cash' }))
  })

  it('shows no Cash choice while it is switched off', async () => {
    mockFetchMembershipTypes.mockResolvedValue(types)
    const wrapper = mount(MembershipDriveView)
    await flushPromises()
    await selectTypeAt(wrapper, 0)
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('Priya Das')
    await inputs[1].setValue('priya@example.com')
    await inputs[2].setValue('41234567')
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.find('.drive-methods').exists()).toBe(false)
  })

  it('lets the volunteer save the signup as "will pay later" without confirming a payment', async () => {
    mockFetchMembershipTypes.mockResolvedValue(types)
    mockSignup.mockResolvedValue({
      member: { id: 1, name: 'Priya Das', email: 'priya@example.com' },
      membership: { id: 1, membership_type: 'Individual', status: 'pending', start_date: '2026-09-28', end_date: null },
      payment: null,
    })

    const wrapper = mount(MembershipDriveView)
    await flushPromises()
    await selectTypeAt(wrapper, 0)
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('Priya Das')
    await inputs[1].setValue('priya@example.com')
    await inputs[2].setValue('41234567')
    await wrapper.find('form').trigger('submit.prevent')

    await wrapper.find('button.pay-later').trigger('click')
    await flushPromises()

    expect(mockSignup).toHaveBeenCalledWith(expect.objectContaining({ payment_method: 'pay_later' }))
    expect(wrapper.find('.pay-later-done').text()).toContain('awaiting payment')
    expect(wrapper.text()).toContain('Not yet')
  })

  it('lets the volunteer continue without a phone number, but not with an invalid one', async () => {
    mockFetchMembershipTypes.mockResolvedValue(types)
    const wrapper = mount(MembershipDriveView)
    await flushPromises()
    await selectTypeAt(wrapper, 0)
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('Priya Das')
    await inputs[1].setValue('priya@example.com')

    await inputs[2].setValue('123')
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.text()).toContain('Enter a valid phone number')

    await inputs[2].setValue('')
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.text()).toContain('Pay with Vipps')
  })
})
