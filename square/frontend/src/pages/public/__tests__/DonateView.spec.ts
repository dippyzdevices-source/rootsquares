// Tests for DonateView (5 cases), e.g. DonateView; shows the square\; keeps only digits and one decimal separator in the amount box.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DonateView from '../DonateView.vue'
import * as api from '../../../services/donationsApi'

vi.mock('../../../services/donationsApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/donationsApi')>()),
  fetchDonationConfig: vi.fn(),
  giveDonation: vi.fn(),
  confirmDonationPayment: vi.fn(),
}))

const config = {
  open: true,
  methods: ['cash'],
  amounts: [10000, 25000],
  min_amount: 100,
  currency: 'NOK',
  intro: 'Help us keep the hall',
  thanks: '',
  vipps_number: '',
  cash_note: 'Hand it to the treasurer.',
  surcharge_percent: 0,
} as api.DonationConfig

describe('DonateView', () => {
  beforeEach(() => vi.resetAllMocks())

  it('shows the square\'s own words and suggested amounts, and sends the chosen amount in minor units', async () => {
    vi.mocked(api.fetchDonationConfig).mockResolvedValue(config)
    vi.mocked(api.giveDonation).mockResolvedValue({ reference: 'DON-2026-000001', amount: 25000, currency: 'NOK', status: 'pending', donor_name: 'Asha' })
    const wrapper = mount(DonateView)
    await flushPromises()
    expect(wrapper.text()).toContain('Help us keep the hall')
    const amounts = wrapper.findAll('.donate-amount')
    expect(amounts).toHaveLength(2)
    await amounts[1].trigger('click')
    const inputs = wrapper.findAll('input.ds-field-input')
    await inputs[1].setValue('Asha')
    await inputs[2].setValue('asha@example.com')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(api.giveDonation).toHaveBeenCalledWith(expect.objectContaining({ amount: 25000, payment_method: 'cash', donor_name: 'Asha' }))
    expect(wrapper.text()).toContain('DON-2026-000001')
    expect(wrapper.text()).toContain('Hand it to the treasurer.')
  })

  it('keeps only digits and one decimal separator in the amount box', async () => {
    vi.mocked(api.fetchDonationConfig).mockResolvedValue(config)
    const wrapper = mount(DonateView)
    await flushPromises()
    const box = wrapper.find('input.donate-custom')
    await box.setValue('12abc.5.678')
    expect((box.element as HTMLInputElement).value).toBe('12.5')
    await box.setValue('x')
    expect((box.element as HTMLInputElement).value).toBe('')
  })

  it('shows the bank details and the reference after a bank transfer gift, leaving empty fields out', async () => {
    vi.mocked(api.fetchDonationConfig).mockResolvedValue({
      ...config,
      methods: ['bank'],
      bank: { holder: 'Asha Club', bank_name: '', account_number: '', iban: 'NO9386011117947', bic: '', note: 'Allow two days' },
    })
    vi.mocked(api.giveDonation).mockResolvedValue({ reference: 'DON-2026-000002', amount: 10000, currency: 'NOK', status: 'pending', donor_name: 'Asha' })
    const wrapper = mount(DonateView)
    await flushPromises()
    await wrapper.findAll('.donate-amount')[0].trigger('click')
    const inputs = wrapper.findAll('input.ds-field-input')
    await inputs[1].setValue('Asha')
    await inputs[2].setValue('asha@example.com')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const text = wrapper.find('.bank-details').text()
    expect(text).toContain('Asha Club')
    expect(text).toContain('NO9386011117947')
    expect(text).not.toContain('BIC')
    expect(text).not.toContain('Bank ')
    expect(wrapper.text()).toContain('DON-2026-000002')
    expect(wrapper.text()).toContain('Allow two days')
    expect(wrapper.find('.donate-reported').exists()).toBe(true)
  })

  it('says donations are not open when no payment method is on', async () => {
    vi.mocked(api.fetchDonationConfig).mockResolvedValue({ ...config, open: false, methods: [] })
    const wrapper = mount(DonateView)
    await flushPromises()
    expect(wrapper.find('.donate-closed').exists()).toBe(true)
    expect(wrapper.find('form').exists()).toBe(false)
  })
})
