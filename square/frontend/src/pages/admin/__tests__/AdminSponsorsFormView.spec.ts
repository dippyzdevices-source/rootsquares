// Tests for AdminSponsorsFormView (2 cases), e.g. AdminSponsorsFormView; saves a second time as an update, not another create.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockCreate = vi.fn()
const mockUpdate = vi.fn()

vi.mock('vue-router', () => ({ useRoute: () => ({ params: {} }) }))
vi.mock('../../../services/adminSponsorsApi', () => ({
  fetchAdminSponsor: vi.fn(),
  createAdminSponsor: (...args: unknown[]) => mockCreate(...args),
  updateAdminSponsor: (...args: unknown[]) => mockUpdate(...args),
  uploadAdminSponsorLogo: vi.fn(),
  ValidationError: class extends Error {},
}))

import AdminSponsorsFormView from '../AdminSponsorsFormView.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => vi.clearAllMocks())

describe('AdminSponsorsFormView', () => {
  it('saves a second time as an update, not another create', async () => {
    const saved = { id: 7, name: 'Acme', logo_url: null, website_url: null, display_order: 0, is_active: true }
    mockCreate.mockResolvedValue(saved)
    mockUpdate.mockResolvedValue(saved)

    const wrapper = mount(AdminSponsorsFormView, { global: { stubs } })
    await flushPromises()
    await wrapper.find('input[placeholder="Acme AS"]').setValue('Acme')

    await wrapper.find('button.save-sponsor').trigger('click')
    await flushPromises()
    await wrapper.find('button.save-sponsor').trigger('click')
    await flushPromises()

    expect(mockCreate).toHaveBeenCalledTimes(1)
    expect(mockUpdate).toHaveBeenCalledTimes(1)
    expect(mockUpdate).toHaveBeenCalledWith(7, expect.objectContaining({ name: 'Acme' }))
  })
})
