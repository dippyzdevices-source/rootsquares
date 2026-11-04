// Tests for VippsReturnView (6 cases), e.g. VippsReturnView; asks the backend to check the payment and shows the paid state; shows a waiting message while Vipps has not confirmed.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockCheck = vi.fn()
let query: Record<string, string> = { ref: 'PAY-1-abc' }

vi.mock('../../../services/vippsAppApi', () => ({
  checkVippsReturn: (...args: unknown[]) => mockCheck(...args),
}))
vi.mock('vue-router', () => ({ useRoute: () => ({ query }) }))

import VippsReturnView from '../VippsReturnView.vue'

const stubs = { BaseButton: { template: '<a><slot /></a>' }, BaseLoadingState: true }

beforeEach(() => {
  vi.clearAllMocks()
  query = { ref: 'PAY-1-abc' }
})

describe('VippsReturnView', () => {
  it('asks the backend to check the payment and shows the paid state', async () => {
    mockCheck.mockResolvedValue({ status: 'paid', order_number: 'BCA-2026-000001' })
    const wrapper = mount(VippsReturnView, { global: { stubs } })
    await flushPromises()
    expect(mockCheck).toHaveBeenCalledWith('PAY-1-abc', false)
    expect(wrapper.find('.vipps-return-paid').text()).toContain('BCA-2026-000001')
  })

  it('shows a waiting message while Vipps has not confirmed', async () => {
    mockCheck.mockResolvedValue({ status: 'initiated', order_number: 'BCA-2026-000001' })
    const wrapper = mount(VippsReturnView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.vipps-return-waiting').exists()).toBe(true)
  })

  it('shows a not-completed message for a failed payment', async () => {
    mockCheck.mockResolvedValue({ status: 'failed', order_number: 'BCA-2026-000001' })
    const wrapper = mount(VippsReturnView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('.vipps-return-failed').text()).toContain("wasn't completed")
  })

  it('names the card payment, not Vipps, and says "you cancelled" when the customer pressed back', async () => {
    mockCheck.mockResolvedValue({ status: 'initiated', order_number: 'BCA-2026-000001', provider: 'stripe' })
    const waiting = mount(VippsReturnView, { global: { stubs } })
    await flushPromises()
    expect(waiting.find('.vipps-return-waiting').text()).toContain('card payment')
    expect(waiting.find('.vipps-return-waiting').text()).not.toContain('Vipps')
    query = { ref: 'cs_1', cancelled: '1' }
    mockCheck.mockResolvedValue({ status: 'cancelled', order_number: 'BCA-2026-000001', provider: 'stripe' })
    const gone = mount(VippsReturnView, { global: { stubs } })
    await flushPromises()
    expect(mockCheck).toHaveBeenLastCalledWith('cs_1', true)
    expect(gone.find('.vipps-return-failed').text()).toContain('You cancelled the payment')
  })

  it('shows an error without calling the API when there is no reference', async () => {
    query = {}
    const wrapper = mount(VippsReturnView, { global: { stubs } })
    await flushPromises()
    expect(mockCheck).not.toHaveBeenCalled()
    expect(wrapper.find('.ds-alert-danger').exists()).toBe(true)
  })
})
