// Tests for BankPaymentPanel (3 cases), e.g. BankPaymentPanel; shows the details that are set, the order number as reference and the; emits report and, once reported, only says it will be confirmed.
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BankPaymentPanel from '../BankPaymentPanel.vue'

const bank = { holder: 'Asha Club', bank_name: '', account_number: '', iban: 'NO9386011117947', bic: '', note: 'Allow two days' }

describe('BankPaymentPanel', () => {
  it('shows the details that are set, the order number as reference and the report button; empty fields stay out', () => {
    const wrapper = mount(BankPaymentPanel, { props: { orderNumber: 'BCA-2026-000001', totalAmount: 30000, paymentStatus: 'pending', bank } })
    const text = wrapper.text()
    expect(text).toContain('Asha Club')
    expect(text).toContain('NO9386011117947')
    expect(text).toContain('BCA-2026-000001')
    expect(text).toContain('Allow two days')
    expect(text).not.toContain('BIC')
    expect(text).not.toContain('Account number')
    expect(wrapper.find('.bank-reported').exists()).toBe(true)
  })

  it('emits report and, once reported, only says it will be confirmed', async () => {
    const wrapper = mount(BankPaymentPanel, { props: { orderNumber: 'X-1', totalAmount: 100, paymentStatus: 'pending', bank } })
    await wrapper.find('.bank-reported').trigger('click')
    expect(wrapper.emitted('report')).toHaveLength(1)
    await wrapper.setProps({ paymentStatus: 'pending_verification' })
    expect(wrapper.find('.bank-reported').exists()).toBe(false)
    expect(wrapper.text()).toContain('we\'ve noted your payment')
  })
})
