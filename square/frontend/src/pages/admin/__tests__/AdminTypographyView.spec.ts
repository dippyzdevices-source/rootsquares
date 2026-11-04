// Tests for AdminTypographyView (3 cases), e.g. AdminTypographyView; saves the chosen description style and applies it to the page straight; shows an error state when the settings cannot be loaded.
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

import AdminTypographyView from '../AdminTypographyView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminSettings.mockResolvedValue({ description_style: 'karla' })
  mockUpdateAdminSettings.mockImplementation(async (payload: object) => ({ description_style: 'karla', ...payload }))
})

describe('AdminTypographyView', () => {
  it('saves the chosen description style and applies it to the page straight away', async () => {
    const wrapper = mount(AdminTypographyView, { global: { stubs } })
    await flushPromises()

    expect((wrapper.find('input[aria-label="Karla (current)"]').element as HTMLInputElement).checked).toBe(true)
    await wrapper.find('input[aria-label="Source Serif 4"]').setValue(true)
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()

    expect(mockUpdateAdminSettings).toHaveBeenCalledWith({ description_style: 'source' })
    expect(document.documentElement.dataset.descStyle).toBe('source')
  })

  it('shows an error state when the settings cannot be loaded', async () => {
    mockFetchAdminSettings.mockRejectedValue(new Error('boom'))
    const wrapper = mount(AdminTypographyView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load the typography settings")
  })
})
