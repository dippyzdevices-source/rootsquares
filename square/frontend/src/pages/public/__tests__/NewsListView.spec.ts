// Tests for NewsListView (12 cases), e.g. NewsListView; shows articles with their summary; shows an empty state when there is no news.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchNews = vi.fn()
const off = vi.hoisted(() => ({ keys: [] as string[] }))
vi.mock('../../../services/modules', () => ({ moduleEnabled: (key?: string) => !off.keys.includes(key ?? '') }))

vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: vi.fn().mockResolvedValue([
    { value: 'announcement', label: 'Announcement' },
    { value: 'story', label: 'Story' },
    { value: 'blog', label: 'Blog' },
  ]),
}))

vi.mock('../../../services/newsApi', () => ({
  fetchNews: (...args: unknown[]) => mockFetchNews(...args),
}))

const mockHomeContent = vi.fn()
vi.mock('../../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/siteContent')>()),
  loadHomeContent: () => mockHomeContent(),
}))

const mockSubscribe = vi.fn()
vi.mock('../../../services/newsletterApi', () => ({
  subscribeNewsletter: (...args: unknown[]) => mockSubscribe(...args),
}))

import { fillHomeContent } from '../../../services/siteContent'
import NewsListView from '../NewsListView.vue'

const BAND = { eyebrow: 'By email', title: 'The newsletter', text: 'Now and then.', consent: 'You agree to get emails.', show_magazines: false }

beforeEach(() => {
  vi.clearAllMocks()
  off.keys = []
  mockHomeContent.mockResolvedValue(fillHomeContent({ news_band: BAND }))
})

describe('NewsListView', () => {
  it('shows articles with their summary', async () => {
    mockFetchNews.mockResolvedValue({
      items: [
        { id: 1, title: 'Membership renewal opens', slug: 'renewal', summary: 'Renew online.', banner_image: null, published_at: '2026-01-01T00:00:00Z' },
      ],
      page: 1,
      per_page: 10,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(NewsListView)
    await flushPromises()

    expect(wrapper.text()).toContain('Membership renewal opens')
    expect(wrapper.text()).toContain('Renew online.')
  })

  it('shows an empty state when there is no news', async () => {
    mockFetchNews.mockResolvedValue({ items: [], page: 1, per_page: 10, total: 0, total_pages: 0 })

    const wrapper = mount(NewsListView)
    await flushPromises()

    expect(wrapper.text()).toContain('No news yet')
  })

  it('shows an error state when the fetch fails', async () => {
    mockFetchNews.mockRejectedValue(new Error('network error'))

    const wrapper = mount(NewsListView)
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load")
  })

  it('shows a category badge on an article that has one', async () => {
    mockFetchNews.mockResolvedValue({
      items: [
        { id: 1, title: 'Renewal opens', slug: 'renewal', summary: null, banner_image: null, category: 'announcement', published_at: null },
      ],
      page: 1, per_page: 10, total: 1, total_pages: 1,
    })

    const wrapper = mount(NewsListView)
    await flushPromises()

    expect(wrapper.text()).toContain('Announcement')
  })

  it('re-fetches with the selected category filter', async () => {
    mockFetchNews.mockResolvedValue({ items: [], page: 1, per_page: 10, total: 0, total_pages: 0 })

    const wrapper = mount(NewsListView)
    await flushPromises()

    await wrapper.findAll('button').find((b) => b.text() === 'Story')!.trigger('click')
    await flushPromises()

    expect(mockFetchNews).toHaveBeenLastCalledWith({ category: 'story', page: 1, perPage: 7 })
  })

  it('names the selected category in the empty state instead of claiming there is no news at all', async () => {
    mockFetchNews.mockResolvedValue({ items: [], page: 1, per_page: 7, total: 0, total_pages: 1 })
    const wrapper = mount(NewsListView)
    await flushPromises()
    expect(wrapper.text()).toContain('No news yet')

    await wrapper.findAll('button.ds-tag').find((b) => b.text() === 'Blog')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('No blog posts yet')
  })

  it('shows a Draft pill on unpublished articles (admin preview), featured and grid alike', async () => {
    mockFetchNews.mockResolvedValue({
      items: [
        { id: 1, title: 'Featured draft', slug: 'a', summary: null, banner_image: null, published_at: null, published: false },
        { id: 2, title: 'Live', slug: 'b', summary: null, banner_image: null, published_at: '2026-01-01T00:00:00Z', published: true },
        { id: 3, title: 'Grid draft', slug: 'c', summary: null, banner_image: null, published_at: null, published: false },
      ],
      page: 1, per_page: 7, total: 3, total_pages: 1,
    })
    const wrapper = mount(NewsListView)
    await flushPromises()

    expect(wrapper.findAll('.draft-pill')).toHaveLength(2)
  })

  it('shows no newsletter band until the square sets one, and no Magazines tab without the module (W7-R5, W8-R14)', async () => {
    off.keys = ['magazines']
    mockFetchNews.mockResolvedValue({ items: [], page: 1, per_page: 7, total: 0, total_pages: 0 })
    mockHomeContent.mockResolvedValue(fillHomeContent(undefined))
    const wrapper = mount(NewsListView)
    await flushPromises()

    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('By post')
    expect(wrapper.find('.tab-magazines').exists()).toBe(false)
  })

  it("shows the square's own band words and consent line, and the Magazines tab only with the module", async () => {
    mockFetchNews.mockResolvedValue({ items: [], page: 1, per_page: 7, total: 0, total_pages: 0 })
    let wrapper = mount(NewsListView)
    await flushPromises()
    expect(wrapper.text()).toContain('The newsletter')
    expect(wrapper.text()).toContain('Now and then.')
    expect(wrapper.text()).toContain('You agree to get emails.')
    expect(wrapper.find('.tab-magazines').exists()).toBe(true) // the Magazines module is on (the default without an answer from the server)

    off.keys = ['magazines']
    mockHomeContent.mockResolvedValue(fillHomeContent({ news_band: { ...BAND, consent: '' } }))
    wrapper = mount(NewsListView)
    await flushPromises()
    expect(wrapper.find('.tab-magazines').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('You agree to get emails.')
  })

  it('subscribes to the newsletter and shows a confirmation', async () => {
    mockFetchNews.mockResolvedValue({ items: [], page: 1, per_page: 7, total: 0, total_pages: 0 })
    mockSubscribe.mockResolvedValue(undefined)
    const wrapper = mount(NewsListView)
    await flushPromises()

    await wrapper.find('form input[type="email"]').setValue(' anna@example.no ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mockSubscribe).toHaveBeenCalledWith('anna@example.no')
    expect(wrapper.find('.newsletter-done').exists()).toBe(true)
  })

  it('shows the error when subscribing fails', async () => {
    mockFetchNews.mockResolvedValue({ items: [], page: 1, per_page: 7, total: 0, total_pages: 0 })
    mockSubscribe.mockRejectedValue(new Error('Enter a valid email address.'))
    const wrapper = mount(NewsListView)
    await flushPromises()

    await wrapper.find('form input[type="email"]').setValue('bad')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Enter a valid email address.')
    expect(wrapper.find('.newsletter-done').exists()).toBe(false)
  })
})
