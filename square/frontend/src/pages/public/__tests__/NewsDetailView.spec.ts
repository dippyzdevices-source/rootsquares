// Tests for NewsDetailView (11 cases), e.g. NewsDetailView; shows the article once loaded; shows a not-found state on a 404.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchNewsArticle = vi.fn()

vi.mock('../../../services/newsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/newsApi')>(
    '../../../services/newsApi',
  )
  return { ...actual, fetchNewsArticle: (...args: unknown[]) => mockFetchNewsArticle(...args) }
})

// A reactive route, so a test can change the slug the way a real navigation would.
vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  const route = reactive({ params: { slug: 'renewal' } })
  return { useRoute: () => route, __route: route }
})

import NewsDetailView from '../NewsDetailView.vue'
import * as vueRouter from 'vue-router'
import { NewsNotFoundError } from '../../../services/newsApi'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('NewsDetailView', () => {
  it('shows the article once loaded', async () => {
    mockFetchNewsArticle.mockResolvedValue({
      id: 1,
      title: 'Membership renewal opens',
      slug: 'renewal',
      summary: null,
      banner_image: null,
      images: [],
      published_at: '2026-01-01T00:00:00Z',
      content: 'Full article body.',
    })

    const wrapper = mount(NewsDetailView)
    await flushPromises()

    expect(wrapper.text()).toContain('Membership renewal opens')
    expect(wrapper.text()).toContain('Full article body.')
  })

  it('shows a not-found state on a 404', async () => {
    mockFetchNewsArticle.mockRejectedValue(new NewsNotFoundError('renewal'))

    const wrapper = mount(NewsDetailView)
    await flushPromises()

    expect(wrapper.text()).toContain('not found')
  })

  it('renders rich text formatting as real HTML', async () => {
    mockFetchNewsArticle.mockResolvedValue({
      id: 1,
      title: 'Membership renewal opens',
      slug: 'renewal',
      summary: null,
      banner_image: null,
      images: [],
      published_at: '2026-01-01T00:00:00Z',
      content: '<h2>Heading</h2><p><strong>Bold</strong> and <em>italic</em>.</p><ul><li>Item</li></ul>',
    })

    const wrapper = mount(NewsDetailView)
    await flushPromises()

    expect(wrapper.find('h2').text()).toBe('Heading')
    expect(wrapper.find('strong').exists()).toBe(true)
    expect(wrapper.find('em').exists()).toBe(true)
    expect(wrapper.find('.news-content li').text()).toBe('Item')
  })

  it('sanitizes any script content out of the article before rendering', async () => {
    mockFetchNewsArticle.mockResolvedValue({
      id: 1,
      title: 'Membership renewal opens',
      slug: 'renewal',
      summary: null,
      banner_image: null,
      images: [],
      published_at: '2026-01-01T00:00:00Z',
      content: '<p>Safe text</p><script>window.hacked = true</script><img src=x onerror="window.hacked = true">',
    })

    const wrapper = mount(NewsDetailView)
    await flushPromises()

    expect(wrapper.html()).not.toContain('<script>')
    expect(wrapper.html()).not.toContain('onerror')
    expect(wrapper.text()).toContain('Safe text')
  })

  it('shows a category badge when the article has one', async () => {
    mockFetchNewsArticle.mockResolvedValue({
      id: 1,
      title: 'Membership renewal opens',
      slug: 'renewal',
      summary: null,
      banner_image: null,
      images: [],
      category: 'story',
      published_at: '2026-01-01T00:00:00Z',
      content: 'Full article body.',
    })

    const wrapper = mount(NewsDetailView)
    await flushPromises()

    expect(wrapper.text()).toContain('Story')
  })

  it('shows a gallery of additional images when the article has them', async () => {
    mockFetchNewsArticle.mockResolvedValue({
      id: 1,
      title: 'Membership renewal opens',
      slug: 'renewal',
      summary: null,
      banner_image: null,
      images: [
        { id: 1, image_url: 'https://x/photo-one.jpg', sort_order: 0 },
        { id: 2, image_url: 'https://x/photo-two.jpg', sort_order: 1 },
      ],
      published_at: '2026-01-01T00:00:00Z',
      content: 'Full article body.',
    })

    const wrapper = mount(NewsDetailView)
    await flushPromises()

    expect(wrapper.text()).toContain('More photos')
    const images = wrapper.findAll('.ds-gallery-item img')
    expect(images).toHaveLength(2)
    expect(images[0].attributes('src')).toBe('https://x/photo-one.jpg')
  })

  it('opens a photo in an in-page viewer (not a new window) and steps through', async () => {
    mockFetchNewsArticle.mockResolvedValue({
      id: 1, title: 'T', slug: 'renewal', summary: null, banner_image: null,
      images: [
        { id: 1, image_url: 'https://x/photo-one.jpg', sort_order: 0 },
        { id: 2, image_url: 'https://x/photo-two.jpg', sort_order: 1 },
      ],
      published_at: '2026-01-01T00:00:00Z', content: 'Body.',
    })
    const wrapper = mount(NewsDetailView)
    await flushPromises()

    const item = wrapper.find('.ds-gallery-item')
    expect(item.element.tagName).toBe('BUTTON')
    await item.trigger('click')

    const body = new DOMWrapper(document.body)
    expect(body.find('.ds-modal img').attributes('src')).toBe('https://x/photo-one.jpg')
    await body.find('button[aria-label="Next photo"]').trigger('click')
    expect(body.find('.ds-modal img').attributes('src')).toBe('https://x/photo-two.jpg')

    wrapper.unmount()
  })

  it('hides the gallery section when the article has no additional images', async () => {
    mockFetchNewsArticle.mockResolvedValue({
      id: 1,
      title: 'Membership renewal opens',
      slug: 'renewal',
      summary: null,
      banner_image: null,
      images: [],
      published_at: '2026-01-01T00:00:00Z',
      content: 'Full article body.',
    })

    const wrapper = mount(NewsDetailView)
    await flushPromises()

    expect(wrapper.text()).not.toContain('More photos')
  })

  it('opens the banner photo in the viewer when clicked', async () => {
    mockFetchNewsArticle.mockResolvedValue({
      id: 1, title: 'Big news', slug: 'renewal', summary: null,
      banner_image: 'https://x/banner.jpg', images: [{ id: 5, image_url: 'https://x/extra.jpg' }],
      published_at: '2026-01-01T00:00:00Z', content: 'Body.',
    })

    const wrapper = mount(NewsDetailView)
    await flushPromises()

    await wrapper.find('button[aria-label="View photo"]').trigger('click')

    const body = new DOMWrapper(document.body)
    expect(body.find('[role="dialog"] img[src="https://x/banner.jpg"]').exists()).toBe(true)
    expect(body.find('button[aria-label="Next photo"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('loads the new article when the route slug changes (a Keep reading link)', async () => {
    mockFetchNewsArticle.mockImplementation(async (slug: string) => ({
      id: 1, title: `Article ${slug}`, slug, summary: null, banner_image: null, images: [],
      published_at: '2026-01-01T00:00:00Z', content: 'Body.',
    }))

    const wrapper = mount(NewsDetailView)
    await flushPromises()
    expect(wrapper.text()).toContain('Article renewal')

    ;(vueRouter as unknown as { __route: { params: { slug: string } } }).__route.params.slug = 'other'
    await flushPromises()

    expect(mockFetchNewsArticle).toHaveBeenLastCalledWith('other')
    expect(wrapper.text()).toContain('Article other')
    ;(vueRouter as unknown as { __route: { params: { slug: string } } }).__route.params.slug = 'renewal'
  })
})
