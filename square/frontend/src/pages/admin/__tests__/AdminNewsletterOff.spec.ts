// Tests for AdminNewsletterOff (2 cases), e.g. admin without the Newsletter module; the News page keeps its heading but has no newsletter band card.
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// A square without the Newsletter module (W8-R15): the News settings page has no newsletter band card.
vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => key !== 'newsletter' }))
vi.mock('../../../services/adminSettingsApi', async () => ({
  ...(await vi.importActual<typeof import('../../../services/adminSettingsApi')>('../../../services/adminSettingsApi')),
  fetchAdminSettings: () => Promise.resolve({ home_content: {} }),
}))
vi.mock('../../../composables/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }))

import AdminPageSettingsView from '../AdminPageSettingsView.vue'

describe('admin without the Newsletter module', () => {
  it('the News page keeps its heading but has no newsletter band card', async () => {
    const wrapper = mount(AdminPageSettingsView, { props: { page: 'news' }, global: { stubs: { SettingsSectionNav: true, SettingsBackButton: true, HeritageMediaCards: true } } })
    await flushPromises()
    expect(wrapper.findAll('h3').map((h) => h.text())).toEqual(['Heading'])
    expect(wrapper.find('[aria-label="News band: Title"]').exists()).toBe(false)
  })
})
