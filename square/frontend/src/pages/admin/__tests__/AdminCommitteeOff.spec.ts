// Tests for AdminCommitteeOff (2 cases), e.g. admin without the Committee module; the About page has no button to the committee page, but keeps the rest.
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Committee module (W8-R12): the About page form does not offer the committee button.
vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => key !== 'committee' }))
vi.mock('../../../services/adminSettingsApi', async () => ({
  ...(await vi.importActual<typeof import('../../../services/adminSettingsApi')>('../../../services/adminSettingsApi')),
  fetchAdminSettings: () => Promise.resolve({ home_content: {} }),
}))
vi.mock('../../../composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }))

import AdminPageSettingsView from '../AdminPageSettingsView.vue'

describe('admin without the Committee module', () => {
  it('the About page has no button to the committee page, but keeps the rest of Who are we', async () => {
    const wrapper = mount(AdminPageSettingsView, { props: { page: 'about' }, global: { stubs: { SettingsSectionNav: true, SettingsBackButton: true, HeritageMediaCards: true } } })
    await flushPromises()
    expect(wrapper.find('[aria-label="About Who are we: Button to the committee page"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="About Who are we: Title"]').exists()).toBe(true)
  })
})
