// Tests for AdminMagazinesListView (2 cases), e.g. AdminMagazinesListView; lists each magazine by its title with its issue and published/draft st.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetch = vi.fn()
vi.mock('../../../services/adminMagazinesApi', () => ({
  fetchAdminMagazines: (...args: unknown[]) => mockFetch(...args),
  deleteAdminMagazine: vi.fn(),
}))

import AdminMagazinesListView from '../AdminMagazinesListView.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => vi.clearAllMocks())

describe('AdminMagazinesListView', () => {
  it('lists each magazine by its title with its issue and published/draft status', async () => {
    mockFetch.mockResolvedValue({
      items: [
        { id: 1, title: 'Puja Special', slug: 'puja-special', issue_label: 'Puja 2026', published: true },
        { id: 2, title: 'Spring Issue', slug: 'spring-issue', issue_label: null, published: false },
      ],
    })
    const wrapper = mount(AdminMagazinesListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('Puja Special')
    expect(wrapper.text()).toContain('Puja 2026')
    expect(wrapper.text()).toContain('Published')
    expect(wrapper.text()).toContain('Spring Issue')
    expect(wrapper.text()).toContain('Draft')
  })
})
