// Tests for AdminPaymentsSettingsView (13 cases), e.g. AdminPaymentsSettingsView; switches Vipps App on for customers and saves it from the unsaved-chan; shows the fees from the settings and saves edited fees (fixed part kro.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchSettings = vi.fn()
const mockUpdateSettings = vi.fn()
const mockVippsStatus = vi.fn()

vi.mock('../../../services/adminSettingsApi', () => ({
  fetchAdminSettings: (...args: unknown[]) => mockFetchSettings(...args),
  updateAdminSettings: (...args: unknown[]) => mockUpdateSettings(...args),
  ValidationError: class extends Error {
    errors: Record<string, string> = {}
  },
}))
vi.mock('../../../services/adminPaymentsApi', () => ({
  fetchVippsStatus: (...args: unknown[]) => mockVippsStatus(...args),
}))

import AdminPaymentsSettingsView from '../AdminPaymentsSettingsView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

const settings = {
  vipps_app_public: false,
  vipps_qr_enabled: true,
  vipps_number: '24680',
  cash_enabled: false,
  cash_ticket_note: '',
  cash_membership_note: '',
  vipps_qr_convenience_percent: 0,
  vipps_qr_processing_percent: 0,
  vipps_qr_processing_fixed_ore: 0,
  vipps_app_convenience_percent: 5,
  vipps_app_processing_percent: 2.99,
  vipps_app_processing_fixed_ore: 100,
  cash_convenience_percent: 0,
  cash_processing_percent: 0,
  cash_processing_fixed_ore: 0,
}

async function mountView() {
  const wrapper = mount(AdminPaymentsSettingsView, { global: { stubs } })
  await flushPromises()
  return wrapper
}
const saveButton = (w: ReturnType<typeof mount>) => w.findAll('button').find((b) => b.text() === 'Save changes')!

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchSettings.mockResolvedValue({ ...settings })
  mockVippsStatus.mockResolvedValue({ configured: true, public: false })
  mockUpdateSettings.mockImplementation(async (payload: object) => ({ ...settings, ...payload }))
})

describe('AdminPaymentsSettingsView', () => {
  it('switches Vipps App on for customers and saves it from the unsaved-changes bar', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.pay-savebar').exists()).toBe(false) // nothing to save yet

    await wrapper.find('input[aria-label="Enable Vipps-App payment"]').setValue(true)
    expect(wrapper.find('.pay-savebar').text()).toContain('unsaved changes')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(mockUpdateSettings).toHaveBeenCalledWith(
      expect.objectContaining({ vipps_app_public: true, vipps_qr_enabled: true, cash_enabled: false }),
    )
    expect(wrapper.find('.pay-savebar').exists()).toBe(false) // saved: bar goes away
  })

  it('shows the fees from the settings and saves edited fees (fixed part kroner -> øre)', async () => {
    const wrapper = await mountView()
    await wrapper.find('input[aria-label="Enable Vipps-App payment"]').setValue(true)

    const app = wrapper.find('[data-method="vipps_app"]')
    const values = app.findAll('input[type="number"]').map((i) => (i.element as HTMLInputElement).value)
    expect(values).toEqual(['5', '2.99', '1'])

    const qr = wrapper.find('[data-method="vipps_qr"]').findAll('input[type="number"]')
    await qr[1].setValue('1.5')
    await qr[2].setValue('0.75')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(mockUpdateSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        vipps_qr_processing_percent: 1.5,
        vipps_qr_processing_fixed_ore: 75,
        vipps_app_convenience_percent: 5,
        vipps_app_processing_fixed_ore: 100,
      }),
    )
  })

  it('Discard puts the saved values back', async () => {
    const wrapper = await mountView()
    const qr = wrapper.find('[data-method="vipps_qr"]').findAll('input[type="number"]')
    await qr[0].setValue('9')
    expect(wrapper.find('.pay-savebar').exists()).toBe(true)

    await wrapper.find('button.discard-changes').trigger('click')
    expect((wrapper.find('[data-method="vipps_qr"]').findAll('input[type="number"]')[0].element as HTMLInputElement).value).toBe('0')
    expect(wrapper.find('.pay-savebar').exists()).toBe(false)
  })

  it('cannot be switched on while Vipps credentials are not configured', async () => {
    mockVippsStatus.mockResolvedValue({ configured: false, public: false })
    const wrapper = await mountView()

    expect(wrapper.find('.vipps-not-configured').exists()).toBe(true)
    expect((wrapper.find('input[aria-label="Enable Vipps-App payment"]').element as HTMLInputElement).disabled).toBe(true)
  })

  it('shows an error state when the settings cannot be loaded', async () => {
    mockFetchSettings.mockRejectedValue(new Error('boom'))
    const wrapper = await mountView()
    expect(wrapper.text()).toContain("Couldn't load the payment settings")
  })

  it('labels how each method is approved, and keeps one method on', async () => {
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Admin approves')
    expect(wrapper.text()).toContain('Auto-approved')

    await wrapper.find('input[aria-label="Enable Vipps-QR payment"]').setValue(false)
    expect(wrapper.find('.no-method-on').exists()).toBe(true)
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('switches Cash on and saves the wording shown to cash payers (with a "use example" shortcut)', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('textarea[aria-label="Cash wording for tickets"]').exists()).toBe(false) // card is off

    await wrapper.find('input[aria-label="Enable Cash payment"]').setValue(true)
    await wrapper.find('textarea[aria-label="Cash wording for tickets"]').setValue('Not confirmed until you pay.')
    await wrapper.find('button.use-example[data-ex="1"]').trigger('click')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(mockUpdateSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        cash_enabled: true,
        cash_ticket_note: 'Not confirmed until you pay.',
        cash_membership_note: 'Pay your membership in cash to a board member.',
      }),
    )
  })

  it('Bank transfer counts as a method only with an account holder and an account number or IBAN, and saves the details', async () => {
    const wrapper = mount(AdminPaymentsSettingsView, { global: { stubs } })
    await flushPromises()
    await wrapper.find('input[aria-label="Enable Vipps-QR payment"]').setValue(false)
    await wrapper.find('input[aria-label="Enable Bank transfer payment"]').setValue(true)
    expect(wrapper.find('.no-method-on').exists()).toBe(true)
    await wrapper.find('input[aria-label="Account holder"]').setValue('Asha Club')
    await wrapper.find('input[aria-label="IBAN"]').setValue('NO9386011117947')
    expect(wrapper.find('.no-method-on').exists()).toBe(false)
    await saveButton(wrapper).trigger('click')
    await flushPromises()
    expect(mockUpdateSettings).toHaveBeenCalledWith(
      expect.objectContaining({ bank_transfer_enabled: true, bank_account_holder: 'Asha Club', bank_iban: 'NO9386011117947' }),
    )
  })

  it('has one tab per way to pay and shows only the cards of the open tab, with a dot on the tabs that are on', async () => {
    const wrapper = await mountView()
    const visible = (sel: string) => (wrapper.find(sel).element as HTMLElement).style.display !== 'none'

    expect(visible('[data-method="vipps_qr"]')).toBe(true) // Vipps is the first tab
    expect(visible('[data-method="vipps_app"]')).toBe(true)
    expect(visible('[data-method="cash"]')).toBe(false)
    expect(visible('[data-method="bank_transfer"]')).toBe(false)
    expect(wrapper.find('[data-tab="vipps"] .pay-tab-on').exists()).toBe(true) // Vipps-QR is on in the test settings
    expect(wrapper.find('[data-tab="cash"] .pay-tab-on').exists()).toBe(false)

    await wrapper.find('[data-tab="cash"]').trigger('click')
    expect(visible('[data-method="cash"]')).toBe(true)
    expect(visible('[data-method="vipps_qr"]')).toBe(false)

    await wrapper.find('[data-tab="bank"]').trigger('click')
    expect(visible('[data-method="bank_transfer"]')).toBe(true)
    expect(visible('.pay-preview')).toBe(false) // bank transfer has no fees to preview
  })

  it('has a Card tab for Stripe: its switch is locked until the account is connected, and it saves the fee', async () => {
    const wrapper = await mountView()
    await wrapper.find('[data-tab="card"]').trigger('click')
    const visible = (sel: string) => (wrapper.find(sel).element as HTMLElement).style.display !== 'none'
    expect(visible('[data-method="stripe"]')).toBe(true)
    expect(visible('[data-method="vipps_qr"]')).toBe(false)
    expect(wrapper.find('input[aria-label="Enable Card (Stripe) payment"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.stripe-not-connected').exists()).toBe(true)
  })

  it('Cash on its own is a valid setup (the "keep one method on" warning stays away)', async () => {
    const wrapper = await mountView()
    await wrapper.find('input[aria-label="Enable Cash payment"]').setValue(true)
    await wrapper.find('input[aria-label="Enable Vipps-QR payment"]').setValue(false)
    expect(wrapper.find('.no-method-on').exists()).toBe(false)
  })

  it('previews what a payment really costs and averages it in the stats', async () => {
    const wrapper = await mountView()
    await wrapper.find('input[aria-label="Enable Vipps-App payment"]').setValue(true)

    // 500 kr + 5% = 525 kr; provider takes 2.99% of 525 + 1 kr = 16.70 kr -> you receive 508.30 kr
    const app = wrapper.find('[data-preview="vipps_app"]')
    expect(app.text()).toContain('525.00 kr')
    expect(app.text()).toContain('−16.70 kr')
    expect(app.text()).toContain('508.30 kr')
    // Vipps-QR is free: customer pays the price, nothing is taken
    expect(wrapper.find('[data-preview="vipps_qr"]').text()).toContain('500.00 kr')
    expect(wrapper.find('.methods-on').text()).toBe('2 of 4')
    expect(wrapper.find('.avg-cost').text()).toContain('8.35 kr') // (16.70 + 0) / 2
    expect(wrapper.find('.avg-extra').text()).toContain('12.50 kr') // (25 + 0) / 2

    await wrapper.find('input[aria-label="Ticket price for the preview"]').setValue('100')
    expect(wrapper.find('[data-preview="vipps_app"]').text()).toContain('105.00 kr')
  })
})
