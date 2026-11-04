// Tests for AccountingContributionModal (4 cases), e.g. AccountingContributionModal; saves a new entry with the amount converted to øre; shows field errors from the server and stays open.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper, type VueWrapper } from '@vue/test-utils'

const mockCreate = vi.fn()
const mockUpdate = vi.fn()

vi.mock('../../../services/adminAccountingApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminAccountingApi')>(
    '../../../services/adminAccountingApi',
  )
  return {
    ...actual,
    createContribution: (...a: unknown[]) => mockCreate(...a),
    updateContribution: (...a: unknown[]) => mockUpdate(...a),
  }
})

import AccountingContributionModal from '../AccountingContributionModal.vue'
import { ValidationError } from '../../../services/adminAccountingApi'

let wrapper: VueWrapper

async function open(contribution: unknown = null) {
  wrapper = mount(AccountingContributionModal, { props: { modelValue: false, eventId: 5, contribution: contribution as never } })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
}

const body = () => new DOMWrapper(document.body)

beforeEach(() => vi.clearAllMocks())
afterEach(() => wrapper.unmount())

describe('AccountingContributionModal', () => {
  it('saves a new entry with the amount converted to øre', async () => {
    mockCreate.mockResolvedValue({ id: 9 })
    await open()
    const inputs = body().findAll('input')
    await inputs[0].setValue('Acme AS') // name
    await inputs[2].setValue('1500') // amount (NOK)
    await inputs[3].setValue('2026-10-02') // date
    await body().find('.save-contribution').trigger('click')
    await flushPromises()

    expect(mockCreate).toHaveBeenCalledWith(
      5,
      expect.objectContaining({ kind: 'donation', name: 'Acme AS', amount: 150000, date: '2026-10-02' }),
    )
    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('shows field errors from the server and stays open', async () => {
    mockCreate.mockRejectedValue(new ValidationError({ name: 'This field is required.' }))
    await open()
    await body().find('.save-contribution').trigger('click')
    await flushPromises()

    expect(body().text()).toContain('This field is required.')
    expect(wrapper.emitted('saved')).toBeFalsy()
  })

  it('edits an existing entry', async () => {
    mockUpdate.mockResolvedValue({ id: 3 })
    await open({ id: 3, kind: 'sponsorship', name: 'Acme AS', email: null, amount: 100000, date: '2026-10-01', payment_method: null, notes: null })
    expect(body().text()).toContain('Edit donation / sponsorship')
    await body().find('.save-contribution').trigger('click')
    await flushPromises()

    expect(mockUpdate).toHaveBeenCalledWith(3, expect.objectContaining({ kind: 'sponsorship', amount: 100000 }))
  })
})
