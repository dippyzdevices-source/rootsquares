// Tests for VippsConnectCard (7 cases), e.g. VippsConnectCard; offers Connect while nothing is connected and says customers cannot pa; shows only non-secret facts once connected.
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockFetch, mockConnect, mockDisconnect } = vi.hoisted(() => ({ mockFetch: vi.fn(), mockConnect: vi.fn(), mockDisconnect: vi.fn() }))

vi.mock('../../services/adminPaymentProvidersApi', async () => {
  const actual = await vi.importActual<typeof import('../../services/adminPaymentProvidersApi')>('../../services/adminPaymentProvidersApi')
  return { ...actual, fetchProviders: mockFetch, connectVipps: mockConnect, disconnectVipps: mockDisconnect }
})
vi.mock('../../composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }))

import VippsConnectCard from '../VippsConnectCard.vue'
import { ProviderKeysError } from '../../services/adminPaymentProvidersApi'

const notConnected = { can_edit: true, providers: { vipps: { provider: 'vipps', connected: false } } }
const connected = {
  can_edit: true,
  providers: { vipps: { provider: 'vipps', connected: true, mode: 'test', hint: { msn: '123456', client_id_last4: 'abcd' }, webhook_registered: false } },
}

async function mountCard() {
  const wrapper = mount(VippsConnectCard, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

async function fill() {
  const set = async (label: string, value: string) => {
    const input = document.body.querySelector(`input[aria-label="${label}"]`) as HTMLInputElement
    input.value = value
    input.dispatchEvent(new Event('input'))
  }
  await set('Merchant serial number', '123456')
  await set('Client ID', 'client-id-1234')
  await set('Client secret', 'the-secret')
  await set('Subscription key', 'the-key')
  await flushPromises()
}

describe('VippsConnectCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
    mockFetch.mockResolvedValue(notConnected)
  })

  it('offers Connect while nothing is connected and says customers cannot pay in the app', async () => {
    const wrapper = await mountCard()
    expect(wrapper.text()).toContain('Not connected')
    expect(wrapper.find('button.vipps-open').text()).toBe('Connect Vipps')
    expect(wrapper.find('button.vipps-disconnect').exists()).toBe(false)
  })

  it('shows only non-secret facts once connected', async () => {
    mockFetch.mockResolvedValue(connected)
    const wrapper = await mountCard()
    expect(wrapper.text()).toContain('Connected in test mode')
    expect(wrapper.text()).toContain('merchant 123456')
    expect(wrapper.text()).toContain('key ending abcd')
    expect(wrapper.find('button.vipps-open').text()).toBe('Replace keys')
  })

  it('sends the keys once, tells the parent, and empties the form', async () => {
    mockConnect.mockResolvedValue(connected)
    const wrapper = await mountCard()
    await wrapper.find('button.vipps-open').trigger('click')
    await fill()
    ;(document.body.querySelector('button.vipps-save') as HTMLButtonElement).click()
    await flushPromises()
    expect(mockConnect).toHaveBeenCalledWith({ client_id: 'client-id-1234', client_secret: 'the-secret', subscription_key: 'the-key', msn: '123456', mode: 'test' })
    expect(wrapper.emitted('changed')?.[0]).toEqual([true])
    expect(document.body.querySelector('input[aria-label="Client secret"]')).toBeNull() // dialog closed, nothing kept
  })

  it('shows what Vipps said when the keys are refused and keeps nothing saved', async () => {
    mockConnect.mockRejectedValue(new ProviderKeysError({ _: 'Vipps did not accept these keys.' }))
    const wrapper = await mountCard()
    await wrapper.find('button.vipps-open').trigger('click')
    await fill()
    ;(document.body.querySelector('button.vipps-save') as HTMLButtonElement).click()
    await flushPromises()
    expect(document.body.querySelector('.vipps-error')?.textContent).toContain('did not accept')
    expect(wrapper.emitted('changed')).toBeUndefined()
  })

  it('keeps replace and disconnect in a danger zone and asks before disconnecting', async () => {
    mockFetch.mockResolvedValue(connected)
    mockDisconnect.mockResolvedValue(notConnected)
    const wrapper = await mountCard()
    expect(wrapper.find('[data-testid="danger-zone"]').exists()).toBe(true)
    await wrapper.find('button.vipps-disconnect').trigger('click')
    expect(mockDisconnect).not.toHaveBeenCalled()
    ;(document.body.querySelector('button.confirm-disconnect') as HTMLButtonElement).click()
    await flushPromises()
    expect(mockDisconnect).toHaveBeenCalledTimes(1)
  })

  it('hides the buttons from an admin who is not the owner', async () => {
    mockFetch.mockResolvedValue({ ...notConnected, can_edit: false })
    const wrapper = await mountCard()
    expect(wrapper.find('button.vipps-open').exists()).toBe(false)
    expect(wrapper.text()).toContain('Only the owner')
  })
})
