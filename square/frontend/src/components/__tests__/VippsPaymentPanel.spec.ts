// Tests for VippsPaymentPanel (4 cases), e.g. VippsPaymentPanel (each square pays to its own Vipps number, rootsquar; shows the square's own number and no QR image; says the payment details are not available when the square has no numb.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchSettings = vi.fn()
vi.mock('../../services/settingsApi', async () => {
  const actual = await vi.importActual<typeof import('../../services/settingsApi')>('../../services/settingsApi')
  return { ...actual, fetchSettings: (...args: unknown[]) => mockFetchSettings(...args) }
})

import VippsPaymentPanel from '../ui/VippsPaymentPanel.vue'

const props = { orderNumber: 'ORD-1', totalAmount: 15000, paymentStatus: 'pending' }

beforeEach(() => vi.clearAllMocks())

describe('VippsPaymentPanel (each square pays to its own Vipps number, rootsquares W6-R38)', () => {
  it("shows the square's own number and no QR image", async () => {
    mockFetchSettings.mockResolvedValue({ vipps_number: '54321' })
    const wrapper = mount(VippsPaymentPanel, { props })
    await flushPromises()
    expect(wrapper.text()).toContain('54321')
    expect(wrapper.text()).not.toContain('24376') // bca-oslo's own number
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('says the payment details are not available when the square has no number, instead of showing someone else\'s', async () => {
    mockFetchSettings.mockResolvedValue({ vipps_number: null })
    const wrapper = mount(VippsPaymentPanel, { props })
    await flushPromises()
    expect(wrapper.text()).toContain('payment details are not available')
    expect(wrapper.text()).not.toContain('24376')
  })

  it('does the same when the settings cannot be loaded', async () => {
    mockFetchSettings.mockRejectedValue(new Error('offline'))
    const wrapper = mount(VippsPaymentPanel, { props })
    await flushPromises()
    expect(wrapper.text()).toContain('payment details are not available')
  })
})
