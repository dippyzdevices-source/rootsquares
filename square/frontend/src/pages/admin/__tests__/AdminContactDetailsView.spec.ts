// Tests for AdminContactDetailsView (3 cases), e.g. AdminContactDetailsView; loads and shows the current contact details; saves edited contact details, sending only the contact fields and the.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminSettings = vi.fn()
const mockUpdateAdminSettings = vi.fn()

vi.mock('../../../services/adminSettingsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminSettingsApi')>(
    '../../../services/adminSettingsApi',
  )
  return {
    ...actual,
    fetchAdminSettings: (...args: unknown[]) => mockFetchAdminSettings(...args),
    updateAdminSettings: (...args: unknown[]) => mockUpdateAdminSettings(...args),
  }
})

const stubs = { RouterLink: { template: '<a><slot /></a>' } }
const BASE = {
  contact_email: 'bengali.culture.oslo@gmail.com',
  contact_phone: '+47 000 00 000',
  contact_address: 'Oslo, Norway',
  maintenance_mode: false,
  maintenance_allowed_event_slugs: 'mahalaya-2026',
  maintenance_allowed_page_paths: '',
  maintenance_hidden_page_paths: '',
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('button').find((b) => b.text() === 'Save')!
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminSettings.mockResolvedValue({ ...BASE })
  mockUpdateAdminSettings.mockImplementation(async (payload: object) => ({ ...BASE, ...payload }))
})

import AdminContactDetailsView from '../AdminContactDetailsView.vue'

describe('AdminContactDetailsView', () => {
  it('loads and shows the current contact details', async () => {
    const wrapper = mount(AdminContactDetailsView, { global: { stubs } })
    await flushPromises()

    const inputs = wrapper.findAll('input')
    expect((inputs[0].element as HTMLInputElement).value).toBe('bengali.culture.oslo@gmail.com')
    expect((inputs[1].element as HTMLInputElement).value).toBe('+47 000 00 000')
    expect((inputs[2].element as HTMLInputElement).value).toBe('Oslo, Norway')
  })

  it('saves edited contact details, sending only the contact fields and the time zone', async () => {
    const wrapper = mount(AdminContactDetailsView, { global: { stubs } })
    await flushPromises()

    await wrapper.findAll('input')[0].setValue('new@bcaoslo.no')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(mockUpdateAdminSettings).toHaveBeenCalledWith({
      contact_email: 'new@bcaoslo.no',
      contact_phone: '+47 000 00 000',
      contact_address: 'Oslo, Norway',
      timezone: 'Europe/Oslo',
    })
  })
})
