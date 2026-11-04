// Tests for AdminSettingsView (7 cases), e.g. AdminSettingsView (site availability); no longer shows the contact details (they have their own page); toggles maintenance mode and sends only the availability fields.
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

function underConstruction() {
  mockFetchAdminSettings.mockResolvedValue({ ...BASE, maintenance_mode: true })
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('button').find((b) => b.text() === 'Save')!
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminSettings.mockResolvedValue({ ...BASE })
  mockUpdateAdminSettings.mockImplementation(async (payload: object) => ({ ...BASE, ...payload }))
})

import AdminSettingsView from '../AdminSettingsView.vue'

describe('AdminSettingsView (site availability)', () => {
  it('no longer shows the contact details (they have their own page)', async () => {
    underConstruction()
    const wrapper = mount(AdminSettingsView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Public contact details')
    expect((wrapper.find('input[type="text"]').element as HTMLInputElement).value).toBe('mahalaya-2026')
  })

  it('toggles maintenance mode and sends only the availability fields', async () => {
    const wrapper = mount(AdminSettingsView, { global: { stubs } })
    await flushPromises()

    const checkbox = wrapper.find('input[type="checkbox"]')
    expect((checkbox.element as HTMLInputElement).checked).toBe(false)
    await checkbox.setValue(true)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(mockUpdateAdminSettings).toHaveBeenCalledWith({
      maintenance_mode: true,
      maintenance_allowed_event_slugs: 'mahalaya-2026',
      maintenance_allowed_page_paths: '',
      maintenance_hidden_page_paths: '',
    })
  })

  it('edits the maintenance-allowed event slug', async () => {
    underConstruction()
    const wrapper = mount(AdminSettingsView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('input[type="text"]').setValue('saraswati-2027')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(mockUpdateAdminSettings).toHaveBeenCalledWith(
      expect.objectContaining({ maintenance_allowed_event_slugs: 'saraswati-2027' }),
    )
  })

  it('sets each main page Published independently of the allowed event slugs', async () => {
    underConstruction()
    const wrapper = mount(AdminSettingsView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('input[aria-label="Home published"]').setValue(true)
    await wrapper.find('input[aria-label="About published"]').setValue(true)
    await wrapper.find('input[aria-label="Events list published"]').setValue(true)
    await wrapper.find('input[aria-label="Events list published"]').setValue(false)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(mockUpdateAdminSettings).toHaveBeenCalledWith(
      expect.objectContaining({ maintenance_allowed_page_paths: 'home,heritage', maintenance_allowed_event_slugs: 'mahalaya-2026' }),
    )
  })

  it('turning a page Visible off hides it and disables its Published switch', async () => {
    underConstruction()
    const wrapper = mount(AdminSettingsView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('input[aria-label="Committee visible"]').setValue(false)
    expect((wrapper.find('input[aria-label="Committee published"]').element as HTMLInputElement).disabled).toBe(true)
    expect((wrapper.find('input[aria-label="Gallery published"]').element as HTMLInputElement).disabled).toBe(false)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(mockUpdateAdminSettings).toHaveBeenCalledWith(
      expect.objectContaining({ maintenance_hidden_page_paths: 'committee' }),
    )
  })

  it('shows a clear "site is live" notice instead of the page settings when the site is not under construction', async () => {
    const wrapper = mount(AdminSettingsView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.site-live-notice').text()).toContain('The site is live')
    expect(wrapper.find('.page-visibility-row').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Allowed event slugs')

    await wrapper.find('input[aria-label="Site under construction"]').setValue(true)
    expect(wrapper.find('.site-live-notice').exists()).toBe(false)
    expect(wrapper.find('.page-visibility-row').exists()).toBe(true)
  })
})
