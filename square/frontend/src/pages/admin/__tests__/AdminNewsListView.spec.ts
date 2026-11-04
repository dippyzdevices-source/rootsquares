// Tests for AdminNewsListView (5 cases), e.g. AdminNewsListView; shows articles with their status badge; shows a humanized category, or a dash when none is set.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchAdminNews = vi.fn()
const mockDeleteAdminNews = vi.fn()

vi.mock('../../../services/adminNewsApi', () => ({
  fetchAdminNews: (...args: unknown[]) => mockFetchAdminNews(...args),
  deleteAdminNews: (...args: unknown[]) => mockDeleteAdminNews(...args),
}))

import AdminNewsListView from '../AdminNewsListView.vue'

beforeEach(() => {
  vi.clearAllMocks()
})

const baseArticle = {
  id: 1,
  title: 'Membership renewal opens',
  slug: 'renewal',
  summary: null,
  content: 'Body',
  banner_image: null,
  status: 'draft',
  published_at: null,
  created_at: '',
  updated_at: '',
}

describe('AdminNewsListView', () => {
  it('shows articles with their status badge', async () => {
    mockFetchAdminNews.mockResolvedValue({
      items: [
        { ...baseArticle, status: 'published' },
        { ...baseArticle, id: 2, title: 'Draft article', status: 'draft' },
      ],
      page: 1,
      per_page: 20,
      total: 2,
      total_pages: 1,
    })

    const wrapper = mount(AdminNewsListView)
    await flushPromises()

    expect(wrapper.text()).toContain('Membership renewal opens')
    expect(wrapper.text()).toContain('Published')
    expect(wrapper.text()).toContain('Draft')
  })

  it('shows a humanized category, or a dash when none is set', async () => {
    mockFetchAdminNews.mockResolvedValue({
      items: [
        { ...baseArticle, category: 'announcement' },
        { ...baseArticle, id: 2, title: 'No category article', category: null },
      ],
      page: 1, per_page: 20, total: 2, total_pages: 1,
    })

    const wrapper = mount(AdminNewsListView)
    await flushPromises()

    expect(wrapper.text()).toContain('Announcement')
    expect(wrapper.text()).toContain('—')
  })

  it('shows an empty state when there are no articles', async () => {
    mockFetchAdminNews.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })

    const wrapper = mount(AdminNewsListView)
    await flushPromises()

    expect(wrapper.text()).toContain('No articles yet')
  })

  it('deletes an article after confirming', async () => {
    mockFetchAdminNews.mockResolvedValue({ items: [baseArticle], page: 1, per_page: 20, total: 1, total_pages: 1 })
    mockDeleteAdminNews.mockResolvedValue(undefined)

    const wrapper = mount(AdminNewsListView)
    await flushPromises()

    await wrapper.find('button[aria-label="Delete Membership renewal opens"]').trigger('click')

    const body = new DOMWrapper(document.body)
    await body.findAll('button').find((b) => b.text() === 'Delete')!.trigger('click')
    await flushPromises()

    expect(mockDeleteAdminNews).toHaveBeenCalledWith(1)

    wrapper.unmount()
  })
})
