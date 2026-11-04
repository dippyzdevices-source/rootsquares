// Tests for EventSupportModals (5 cases), e.g. DonateModal; needs an amount, then sends it in øre with the chosen method (name opt; shows server field errors.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper, type VueWrapper } from '@vue/test-utils'

const mockDonate = vi.fn()
const mockEnquire = vi.fn()

vi.mock('../../services/eventSupportApi', () => ({
  donate: (...a: unknown[]) => mockDonate(...a),
  enquireSponsorship: (...a: unknown[]) => mockEnquire(...a),
}))

import DonateModal from '../DonateModal.vue'
import SponsorEnquiryModal from '../SponsorEnquiryModal.vue'
import { ValidationError } from '../../services/membershipDriveApi'

let wrapper: VueWrapper
const body = () => new DOMWrapper(document.body)

async function open(component: unknown, props: Record<string, unknown>) {
  wrapper = mount(component as never, { props: { modelValue: false, slug: 'durga-puja', eventTitle: 'Durga Puja', ...props } as never })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
}

beforeEach(() => vi.clearAllMocks())
afterEach(() => wrapper.unmount())

describe('DonateModal', () => {
  it('needs an amount, then sends it in øre with the chosen method (name optional)', async () => {
    mockDonate.mockResolvedValue({ payment_method: 'vipps_qr', redirect_url: null })
    await open(DonateModal, { methods: ['vipps_app', 'vipps_qr'] })

    await body().find('form').trigger('submit')
    expect(mockDonate).not.toHaveBeenCalled()
    expect(body().text()).toContain('Enter an amount.')

    const presets = body().findAll('button.ds-tag')
    await presets[1].trigger('click') // 250 kr
    await body().findAll('input[type=radio]')[1].setValue(true) // Vipps QR
    await body().find('form').trigger('submit')
    await flushPromises()

    expect(mockDonate).toHaveBeenCalledWith('durga-puja', {
      name: undefined, email: undefined, amount: 25000, payment_method: 'vipps_qr',
    })
    expect(body().text()).toContain('Thank you for supporting Durga Puja')
  })

  it('shows server field errors', async () => {
    mockDonate.mockRejectedValue(new ValidationError({ email: 'Enter a valid email address.' }))
    await open(DonateModal, { methods: ['vipps_qr'] })
    await body().findAll('button.ds-tag')[0].trigger('click')
    await body().find('form').trigger('submit')
    await flushPromises()
    expect(body().text()).toContain('Enter a valid email address.')
  })
})

describe('SponsorEnquiryModal', () => {
  it('requires company, contact person and email, then sends the enquiry', async () => {
    mockEnquire.mockResolvedValue({ ok: true })
    await open(SponsorEnquiryModal, {})

    await body().find('form').trigger('submit')
    expect(mockEnquire).not.toHaveBeenCalled()

    const inputs = body().findAll('input')
    await inputs[0].setValue('Acme AS')
    await inputs[1].setValue('Ola Nordmann')
    await inputs[2].setValue('ola@acme.no')
    await body().find('textarea').setValue('Logo on the stage banner')
    await body().find('form').trigger('submit')
    await flushPromises()

    expect(mockEnquire).toHaveBeenCalledWith(
      'durga-puja',
      expect.objectContaining({ name: 'Acme AS', contact_name: 'Ola Nordmann', email: 'ola@acme.no', requirements: 'Logo on the stage banner' }),
    )
    expect(body().text()).toContain('Thank you for offering to sponsor')
  })
})
