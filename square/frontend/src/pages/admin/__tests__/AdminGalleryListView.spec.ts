// Tests for AdminGalleryListView (5 cases), e.g. AdminGalleryListView; shows albums with a published/draft badge; shows each album\.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchAdminAlbums = vi.fn()
const mockDeleteAdminAlbum = vi.fn()

vi.mock('../../../services/adminGalleryApi', () => ({
  fetchAdminAlbums: (...args: unknown[]) => mockFetchAdminAlbums(...args),
  deleteAdminAlbum: (...args: unknown[]) => mockDeleteAdminAlbum(...args),
}))

import AdminGalleryListView from '../AdminGalleryListView.vue'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AdminGalleryListView', () => {
  it('shows albums with a published/draft badge', async () => {
    mockFetchAdminAlbums.mockResolvedValue({
      items: [
        { id: 1, title: 'Durga Puja 2026', description: null, event_id: null, published: true, created_at: '', updated_at: '', media: [] },
        { id: 2, title: 'Draft album', description: null, event_id: null, published: false, created_at: '', updated_at: '', media: [] },
      ],
      page: 1,
      per_page: 20,
      total: 2,
      total_pages: 1,
    })

    const wrapper = mount(AdminGalleryListView)
    await flushPromises()

    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).toContain('Published')
    expect(wrapper.text()).toContain('Draft')
  })

  it('shows each album\'s category, or a dash when uncategorized', async () => {
    mockFetchAdminAlbums.mockResolvedValue({
      items: [
        { id: 1, title: 'Durga Puja 2026', description: null, event_id: null, category: 'festivals', published: true, created_at: '', updated_at: '', media: [] },
        { id: 2, title: 'Uncategorized album', description: null, event_id: null, category: null, published: true, created_at: '', updated_at: '', media: [] },
      ],
      page: 1, per_page: 20, total: 2, total_pages: 1,
    })

    const wrapper = mount(AdminGalleryListView)
    await flushPromises()

    expect(wrapper.text()).toContain('Festivals')
    expect(wrapper.text()).toContain('—')
  })

  it('shows an empty state when there are no albums', async () => {
    mockFetchAdminAlbums.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })

    const wrapper = mount(AdminGalleryListView)
    await flushPromises()

    expect(wrapper.text()).toContain('No albums yet')
  })

  it('deletes an album after confirming', async () => {
    mockFetchAdminAlbums.mockResolvedValue({
      items: [{ id: 1, title: 'Durga Puja 2026', description: null, event_id: null, published: true, created_at: '', updated_at: '', media: [] }],
      page: 1,
      per_page: 20,
      total: 1,
      total_pages: 1,
    })
    mockDeleteAdminAlbum.mockResolvedValue(undefined)

    const wrapper = mount(AdminGalleryListView)
    await flushPromises()

    await wrapper.find('button[aria-label="Delete Durga Puja 2026"]').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.findAll('button').find((b) => b.text() === 'Delete')!.trigger('click')
    await flushPromises()

    expect(mockDeleteAdminAlbum).toHaveBeenCalledWith(1)

    wrapper.unmount()
  })
})
