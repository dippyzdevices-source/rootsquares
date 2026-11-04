// Tests for AdminHomeContentView (3 cases), e.g. AdminHomeContentView (W6-R64); shows what is saved, with three number rows; saves only the home content.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminSettings = vi.fn()
const mockUpdateAdminSettings = vi.fn()

vi.mock('../../../services/adminSettingsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminSettingsApi')>('../../../services/adminSettingsApi')
  return {
    ...actual,
    fetchAdminSettings: (...args: unknown[]) => mockFetchAdminSettings(...args),
    updateAdminSettings: (...args: unknown[]) => mockUpdateAdminSettings(...args),
  }
})
vi.mock('../../../composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }))

import AdminHomeContentView from '../AdminHomeContentView.vue'

const stubs = { SettingsSectionNav: true, RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminSettings.mockResolvedValue({ home_content: { headline: 'Hello', stats: [{ value: '16', label: 'years' }] } })
  mockUpdateAdminSettings.mockImplementation(async (payload: { home_content: object }) => ({ home_content: payload.home_content }))
})

describe('AdminHomeContentView (W6-R64)', () => {
  it('shows what is saved, with three number rows', async () => {
    const wrapper = mount(AdminHomeContentView, { global: { stubs } })
    await flushPromises()
    const headline = wrapper.get('input[aria-label="Headline"]').element as HTMLInputElement
    expect(headline.value).toBe('Hello')
    expect(wrapper.findAll('input[aria-label^="Number"]')).toHaveLength(3)
    expect((wrapper.get('input[aria-label="Label 1"]').element as HTMLInputElement).value).toBe('years')
  })

  it('saves only the home content', async () => {
    const wrapper = mount(AdminHomeContentView, { global: { stubs } })
    await flushPromises()
    await wrapper.get('input[aria-label="Headline"]').setValue('Bengal, kept alive in Oslo')
    await wrapper.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    expect(mockUpdateAdminSettings).toHaveBeenCalledTimes(1)
    const payload = mockUpdateAdminSettings.mock.calls[0][0] as { home_content: { headline: string } }
    expect(Object.keys(payload)).toEqual(['home_content'])
    expect(payload.home_content.headline).toBe('Bengal, kept alive in Oslo')
  })
})
