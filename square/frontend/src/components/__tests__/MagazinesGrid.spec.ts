// Tests for MagazinesGrid (4 cases), e.g. MagazinesGrid; shows an empty state when there are no magazines; shows an error state when loading fails.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchMagazines = vi.fn()
vi.mock('../../services/magazinesApi', () => ({
  fetchMagazines: (...args: unknown[]) => mockFetchMagazines(...args),
}))

import MagazinesGrid from '../MagazinesGrid.vue'

const stubs = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

beforeEach(() => vi.clearAllMocks())

describe('MagazinesGrid', () => {
  it('shows an empty state when there are no magazines', async () => {
    mockFetchMagazines.mockResolvedValue([])
    const wrapper = mount(MagazinesGrid, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('No magazines yet')
  })

  it('shows an error state when loading fails', async () => {
    mockFetchMagazines.mockRejectedValue(new Error('boom'))
    const wrapper = mount(MagazinesGrid, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('Could not load magazines')
  })

  it('links each magazine to its reader page and tags drafts', async () => {
    mockFetchMagazines.mockResolvedValue([
      { id: 1, title: 'Puja Special', slug: 'puja-special', issue_label: 'Puja 2026', issue_date: null, description: null, pdf_url: 'https://cdn/x.pdf', cover_url: 'https://cdn/c.jpg' },
      { id: 2, title: 'Hidden', slug: 'hidden', issue_label: null, issue_date: null, description: null, pdf_url: 'https://cdn/y.pdf', cover_url: null, published: false },
    ])
    const wrapper = mount(MagazinesGrid, { global: { stubs } })
    await flushPromises()

    const links = wrapper.findAll('a')
    expect(links.map((a) => a.attributes('href'))).toEqual(['/news/magazines/puja-special', '/news/magazines/hidden'])
    expect(wrapper.text()).toContain('Puja 2026')
    expect(links[1].text()).toContain('Draft')
  })
})
