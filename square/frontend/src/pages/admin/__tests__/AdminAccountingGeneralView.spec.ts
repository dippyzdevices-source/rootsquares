// Tests for AdminAccountingGeneralView (6 cases), e.g. AdminAccountingGeneralView; asks for a year before showing the budget, then saves an amount in min; saves an income target in minor units, shows what is still to raise an.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const summary = vi.fn()
const income = vi.fn()
const expenses = vi.fn()
const remove = vi.fn()
const fetchBudget = vi.fn()
const saveBudget = vi.fn()
const saveTarget = vi.fn()
const copyBudget = vi.fn()

vi.mock('../../../services/lookupsApi', () => ({ fetchLookup: vi.fn().mockResolvedValue([{ value: 'venue', label: 'Venue' }]) }))
vi.mock('../../../services/adminAccountingApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/adminAccountingApi')>()),
  fetchGeneralSummary: (...a: unknown[]) => summary(...a),
  fetchGeneralIncome: (...a: unknown[]) => income(...a),
  fetchEventExpenses: (...a: unknown[]) => expenses(...a),
  deleteExpense: (...a: unknown[]) => remove(...a),
  fetchGeneralBudget: (...a: unknown[]) => fetchBudget(...a),
  setGeneralBudget: (...a: unknown[]) => saveBudget(...a),
  setGeneralIncomeTarget: (...a: unknown[]) => saveTarget(...a),
  copyGeneralBudget: (...a: unknown[]) => copyBudget(...a),
}))

import AdminAccountingGeneralView from '../AdminAccountingGeneralView.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' }, AccountingExpenseModal: true, AccountingExpenseViewModal: true, AccountingReceiptModal: true }

beforeEach(() => {
  vi.clearAllMocks()
  summary.mockResolvedValue({
    currency: 'NOK',
    income: { total: 90000, by_source: [{ source: 'donation', label: 'Donations', count: 2, total: 60000 }] },
    expenses: { total: 25000, count: 1, by_category: [{ category: 'venue', label: 'Venue', total: 25000 }] },
    net: 65000,
  })
  income.mockResolvedValue([{ source: 'donation', reference: 'DON-1', name: 'Asha', date: '2026-05-10', amount: 50000 }])
  expenses.mockResolvedValue({ items: [{ id: 7, event_id: null, date: '2026-05-02', description: 'Hall rent', category: 'venue', amount: 25000, vendor: null, notes: null, receipt_key: null, receipt_url: null, created_by: null, created_at: '', updated_at: '' }] })
})

describe('AdminAccountingGeneralView', () => {
  it('asks for a year before showing the budget, then saves an amount in minor units and reloads', async () => {
    fetchBudget.mockResolvedValue({ year: 2026, currency: 'NOK', items: [{ category: 'venue', label: 'Venue', budget: 0, spent: 25000, remaining: -25000 }], budget_total: 0, spent_total: 25000, income: [], income_target_total: 0, income_received_total: 0, planned_net: 0 })
    saveBudget.mockResolvedValue(undefined)
    const wrapper = mount(AdminAccountingGeneralView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.budget-section').text()).toContain('Choose a year')
    expect(fetchBudget).not.toHaveBeenCalled()
    ;(wrapper.vm as unknown as { year: string }).year = '2026'
    await flushPromises()
    expect(fetchBudget).toHaveBeenCalledWith(2026)
    const input = wrapper.find('.budget-input')
    ;(input.element as HTMLInputElement).value = '1500.50'
    await input.trigger('change')
    await flushPromises()
    expect(saveBudget).toHaveBeenCalledWith(2026, 'venue', 150050)
    expect(fetchBudget).toHaveBeenCalledTimes(2)
  })

  it('saves an income target in minor units, shows what is still to raise and the planned result', async () => {
    fetchBudget.mockResolvedValue({
      year: 2026,
      currency: 'NOK',
      items: [],
      budget_total: 100000,
      spent_total: 0,
      income: [{ source: 'donation', label: 'Donations', target: 150000, received: 60000, remaining: 90000 }],
      income_target_total: 150000,
      income_received_total: 60000,
      planned_net: 50000,
    })
    saveTarget.mockResolvedValue(undefined)
    const wrapper = mount(AdminAccountingGeneralView, { global: { stubs } })
    await flushPromises()
    ;(wrapper.vm as unknown as { year: string }).year = '2026'
    await flushPromises()
    expect(wrapper.find('.budget-section').text()).toContain('Still to raise')
    expect(wrapper.find('[data-testid="planned-net"]').text()).toContain('Planned result for 2026')
    const input = wrapper.find('input[aria-label="Target for Donations"]')
    ;(input.element as HTMLInputElement).value = '2000'
    await input.trigger('change')
    await flushPromises()
    expect(saveTarget).toHaveBeenCalledWith(2026, 'donation', 200000)
    expect(fetchBudget).toHaveBeenCalledTimes(2)
  })

  it('copies last year into the chosen year and reloads the budget', async () => {
    fetchBudget.mockResolvedValue({ year: 2026, currency: 'NOK', items: [], budget_total: 0, spent_total: 0, income: [], income_target_total: 0, income_received_total: 0, planned_net: 0 })
    copyBudget.mockResolvedValue({ year: 2026, from_year: 2025, budgets: 2, targets: 1 })
    const wrapper = mount(AdminAccountingGeneralView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.copy-last-year').exists()).toBe(false)
    ;(wrapper.vm as unknown as { year: string }).year = '2026'
    await flushPromises()
    expect(wrapper.find('.copy-last-year').text()).toContain('Copy from 2025')
    await wrapper.find('.copy-last-year').trigger('click')
    await flushPromises()
    expect(copyBudget).toHaveBeenCalledWith(2026)
    expect(fetchBudget).toHaveBeenCalledTimes(2)
  })

  it('shows income, expenses and net of the general book, and asks for the no-event book (event id null)', async () => {
    const wrapper = mount(AdminAccountingGeneralView, { global: { stubs } })
    await flushPromises()
    expect(expenses).toHaveBeenCalledWith(null, expect.objectContaining({ perPage: 50 }))
    expect(wrapper.text()).toContain('General accounts')
    expect(wrapper.text()).toContain('DON-1')
    expect(wrapper.text()).toContain('Hall rent')
    expect(wrapper.find('.general-net').exists()).toBe(true)
  })

  it('deletes an expense after confirmation and reloads', async () => {
    remove.mockResolvedValue(undefined)
    const wrapper = mount(AdminAccountingGeneralView, { global: { stubs }, attachTo: document.body })
    await flushPromises()
    await wrapper.find('.delete-expense').trigger('click')
    await flushPromises()
    ;(document.body.querySelector('.confirm-delete') as HTMLElement).click()
    await flushPromises()
    expect(remove).toHaveBeenCalledWith(7)
    expect(summary).toHaveBeenCalledTimes(2)
    wrapper.unmount()
    document.body.innerHTML = ''
  })
})
