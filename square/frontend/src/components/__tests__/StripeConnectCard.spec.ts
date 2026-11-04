// Tests for StripeConnectCard (7 cases), e.g. StripeConnectCard; offers Connect while nothing is connected and tells the page it is not; shows only non-secret facts once connected.
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockFetch, mockConnect, mockDisconnect } = vi.hoisted(() => ({ mockFetch: vi.fn(), mockConnect: vi.fn(), mockDisconnect: vi.fn() }))

vi.mock('../../services/adminPaymentProvidersApi', async () => {
  const actual = await vi.importActual<typeof import('../../services/adminPaymentProvidersApi')>('../../services/adminPaymentProvidersApi')
  return { ...actual, fetchProviders: mockFetch, connectStripe: mockConnect, disconnectStripe: mockDisconnect }
})
vi.mock('../../composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }))

import StripeConnectCard from '../StripeConnectCard.vue'
import { ProviderKeysError } from '../../services/adminPaymentProvidersApi'

const vipps = { provider: 'vipps', connected: false }
const notConnected = { can_edit: true, providers: { vipps, stripe: { provider: 'stripe', connected: false } } }
const connected = {
  can_edit: true,
  providers: { vipps, stripe: { provider: 'stripe', connected: true, mode: 'test', hint: { key_last4: '6789', restricted: true }, webhook_registered: true } },
}

async function mountCard() {
  const wrapper = mount(StripeConnectCard, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

function typeKey(value: string) {
  const input = document.body.querySelector('input[aria-label="Stripe key"]') as HTMLInputElement
  input.value = value
  input.dispatchEvent(new Event('input'))
}

describe('StripeConnectCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
    mockFetch.mockResolvedValue(notConnected)
  })

  it('offers Connect while nothing is connected and tells the page it is not connected', async () => {
    const wrapper = await mountCard()
    expect(wrapper.text()).toContain('Not connected')
    expect(wrapper.find('button.stripe-open').text()).toBe('Connect Stripe')
    expect(wrapper.emitted('changed')?.[0]).toEqual([false])
  })

  it('shows only non-secret facts once connected', async () => {
    mockFetch.mockResolvedValue(connected)
    const wrapper = await mountCard()
    expect(wrapper.text()).toContain('Connected in test mode')
    expect(wrapper.text()).toContain('key ending 6789')
    expect(wrapper.text()).toContain('restricted key')
    expect(wrapper.emitted('changed')?.[0]).toEqual([true])
  })

  it('sends the key once, tells the parent, and empties the form', async () => {
    mockConnect.mockResolvedValue(connected)
    const wrapper = await mountCard()
    await wrapper.find('button.stripe-open').trigger('click')
    typeKey('rk_test_abc')
    await flushPromises()
    ;(document.body.querySelector('button.stripe-save') as HTMLButtonElement).click()
    await flushPromises()
    expect(mockConnect).toHaveBeenCalledWith('rk_test_abc', { webhookSecret: '', managedPayments: false, taxCode: '' })
    expect(wrapper.emitted('changed')?.at(-1)).toEqual([true])
    expect(document.body.querySelector('input[aria-label="Stripe key"]')).toBeNull()
  })

  it('shows what Stripe said when the key is refused', async () => {
    mockConnect.mockRejectedValue(new ProviderKeysError({ _: 'Stripe did not accept this key.' }))
    const wrapper = await mountCard()
    await wrapper.find('button.stripe-open').trigger('click')
    typeKey('rk_test_bad')
    await flushPromises()
    ;(document.body.querySelector('button.stripe-save') as HTMLButtonElement).click()
    await flushPromises()
    expect(document.body.querySelector('.stripe-error')?.textContent).toContain('did not accept')
  })

  it('keeps replace and disconnect in a danger zone and asks before disconnecting', async () => {
    mockFetch.mockResolvedValue(connected)
    mockDisconnect.mockResolvedValue(notConnected)
    const wrapper = await mountCard()
    expect(wrapper.find('[data-testid="danger-zone"]').exists()).toBe(true)
    await wrapper.find('button.stripe-disconnect').trigger('click')
    expect(mockDisconnect).not.toHaveBeenCalled()
    ;(document.body.querySelector('button.confirm-disconnect') as HTMLButtonElement).click()
    await flushPromises()
    expect(mockDisconnect).toHaveBeenCalledTimes(1)
  })

  it('hides the buttons from an admin who is not the owner', async () => {
    mockFetch.mockResolvedValue({ ...notConnected, can_edit: false })
    const wrapper = await mountCard()
    expect(wrapper.find('button.stripe-open').exists()).toBe(false)
    expect(wrapper.text()).toContain('Only the owner')
  })
})
