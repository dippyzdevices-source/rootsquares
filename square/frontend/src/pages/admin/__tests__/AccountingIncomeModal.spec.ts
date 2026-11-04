// Tests for AccountingIncomeModal (4 cases), e.g. AccountingIncomeModal; adds income, sending the amount in minor units; changes an income typed in earlier.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper, type VueWrapper } from '@vue/test-utils'

const mockCreate = vi.fn()
const mockUpdate = vi.fn()

vi.mock('../../../services/adminAccountingApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminAccountingApi')>('../../../services/adminAccountingApi')
  return { ...actual, createManualIncome: (...a: unknown[]) => mockCreate(...a), updateManualIncome: (...a: unknown[]) => mockUpdate(...a) }
})

import AccountingIncomeModal from '../AccountingIncomeModal.vue'
import { ValidationError, type GeneralIncomeRow } from '../../../services/adminAccountingApi'

let current: VueWrapper | null = null
beforeEach(() => vi.clearAllMocks())
afterEach(() => {
  current?.unmount()
  current = null
})

async function mountOpen(income: GeneralIncomeRow | null) {
  const wrapper = mount(AccountingIncomeModal, { props: { modelValue: false, income } })
  current = wrapper
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}
const body = () => new DOMWrapper(document.body)
const save = async () => {
  await body().find('.save-income').trigger('click')
  await flushPromises()
}

describe('AccountingIncomeModal', () => {
  it('adds income, sending the amount in minor units', async () => {
    mockCreate.mockResolvedValue({ id: 1 })
    const wrapper = await mountOpen(null)
    await body().find('.income-date').setValue('2026-05-02')
    await body().find('.income-description').setValue('Hall hire')
    await body().find('.income-amount').setValue('1500.5')
    await save()
    expect(mockCreate).toHaveBeenCalledWith({ date: '2026-05-02', description: 'Hall hire', amount: 150050, source_name: null, notes: null })
    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('changes an income typed in earlier', async () => {
    mockUpdate.mockResolvedValue({ id: 7 })
    await mountOpen({ source: 'manual', id: 7, reference: 'Grant', name: 'Council', date: '2026-04-01', amount: 100000, notes: 'Yearly' })
    expect((body().find('.income-description').element as HTMLInputElement).value).toBe('Grant')
    await body().find('.income-amount').setValue('1200')
    await save()
    expect(mockUpdate).toHaveBeenCalledWith(7, { date: '2026-04-01', description: 'Grant', amount: 120000, source_name: 'Council', notes: 'Yearly' })
  })

  it('shows the server message under the field', async () => {
    mockCreate.mockRejectedValue(new ValidationError({ amount: 'Must be a number greater than zero.' }))
    await mountOpen(null)
    await save()
    expect(document.body.textContent).toContain('Must be a number greater than zero.')
  })
})
