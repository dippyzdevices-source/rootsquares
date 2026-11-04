// Tests for AdminSponsorsOff (2 cases), e.g. admin without the Sponsors module; the Home page form has no sponsor words, but keeps the others.
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Sponsors module (W8-R11): no sponsor words on the Home page form.
vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => key !== 'sponsors' }))
vi.mock('../../../services/adminSettingsApi', async () => ({
  ...(await vi.importActual<typeof import('../../../services/adminSettingsApi')>('../../../services/adminSettingsApi')),
  fetchAdminSettings: () => Promise.resolve({ home_content: {} }),
}))
vi.mock('../../../composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }))

import AdminHomeContentView from '../AdminHomeContentView.vue'

const stubs = { SettingsSectionNav: true, SettingsBackButton: true }

describe('admin without the Sponsors module', () => {
  it('the Home page form has no sponsor words, but keeps the others', async () => {
    const wrapper = mount(AdminHomeContentView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('[aria-label="Small line above the sponsors"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Heading above the sponsors"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Small line above the testimonial"]').exists()).toBe(true)
  })
})
