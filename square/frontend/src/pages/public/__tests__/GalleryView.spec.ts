// Tests for GalleryView (12 cases), e.g. GalleryView; shows published albums with their cover and photo count; shows an album's real category tag on its card, not a generic label.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAlbums = vi.fn()
const mockFetchArchiveCoverage = vi.fn()
const mockHomeContent = vi.fn()

vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: vi.fn().mockResolvedValue([
    { value: 'festivals', label: 'Festivals' },
    { value: 'community', label: 'Community' },
    { value: 'archive', label: 'Archive' },
  ]),
}))

vi.mock('../../../services/galleryApi', () => ({
  fetchAlbums: (...args: unknown[]) => mockFetchAlbums(...args),
  fetchArchiveCoverage: () => mockFetchArchiveCoverage(),
}))

vi.mock('../../../services/siteContent', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/siteContent')>()),
  loadHomeContent: () => mockHomeContent(),
}))

import { fillHomeContent } from '../../../services/siteContent'
import GalleryView from '../GalleryView.vue'

// RouterLink is deliberately left unstubbed here — VTU's auto-stub swallows the
// default slot content (the album card), which is exactly what these tests assert on.
beforeEach(() => {
  vi.clearAllMocks()
  mockFetchArchiveCoverage.mockResolvedValue([])
  mockHomeContent.mockResolvedValue(fillHomeContent(undefined))
})

describe('GalleryView', () => {
  it('shows published albums with their cover and photo count', async () => {
    mockFetchAlbums.mockResolvedValue({
      items: [
        { id: 1, title: 'Durga Puja 2026', description: null, cover_thumbnail_url: 'https://x/cover.jpg', photo_count: 12 },
      ],
      page: 1,
      per_page: 20,
      total: 1,
      total_pages: 1,
    })

    const wrapper = mount(GalleryView)
    await flushPromises()

    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.text()).toContain('12')
  })

  it("shows an album's real category tag on its card, not a generic label", async () => {
    mockFetchAlbums.mockResolvedValue({
      items: [
        { id: 1, title: 'Durga Puja 2026', description: null, category: 'festivals', cover_thumbnail_url: null, photo_count: 12 },
        { id: 2, title: 'Uncategorized', description: null, category: null, cover_thumbnail_url: null, photo_count: 3 },
      ],
      page: 1, per_page: 20, total: 2, total_pages: 1,
    })

    const wrapper = mount(GalleryView)
    await flushPromises()

    expect(wrapper.text()).toContain('Festivals')
    expect(wrapper.text()).not.toContain('Photos')
  })

  it('shows an empty state when there are no albums', async () => {
    mockFetchAlbums.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 })

    const wrapper = mount(GalleryView)
    await flushPromises()

    expect(wrapper.text()).toContain('No albums yet')
  })

  it('shows an error state when the fetch fails', async () => {
    mockFetchAlbums.mockRejectedValue(new Error('network error'))

    const wrapper = mount(GalleryView)
    await flushPromises()

    expect(wrapper.text()).toContain("Couldn't load")
  })

  it('re-fetches with the selected category and resets to page 1', async () => {
    mockFetchAlbums.mockResolvedValue({ items: [], page: 1, per_page: 20, total: 0, total_pages: 1 })

    const wrapper = mount(GalleryView)
    await flushPromises()

    expect(mockFetchAlbums).toHaveBeenCalledWith(1, 12, undefined, undefined)

    await wrapper.find('button.ds-tag:nth-of-type(2)').trigger('click')
    await flushPromises()

    expect(mockFetchAlbums).toHaveBeenLastCalledWith(1, 12, undefined, 'festivals')
  })

  it('only shows albums matching the selected category', async () => {
    mockFetchAlbums.mockResolvedValue({
      items: [
        { id: 1, title: 'Durga Puja 2026', description: null, category: 'festivals', cover_thumbnail_url: null, photo_count: 3 },
      ],
      page: 1, per_page: 20, total: 1, total_pages: 1,
    })

    const wrapper = mount(GalleryView)
    await flushPromises()
    await wrapper.findAll('button.ds-tag').find((b) => b.text() === 'Festivals')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Durga Puja 2026')
  })

  const NO_ALBUMS = { items: [], page: 1, per_page: 12, total: 0, total_pages: 1 }
  const ERAS = [
    { era: '2010–2014', start_year: 2010, end_year: 2014, photo_count: 0, state: 'none' },
    { era: '2015–2019', start_year: 2015, end_year: 2019, photo_count: 150, state: 'complete' },
  ]

  it('shows no bottom band, and does not ask for coverage, until the square sets a title (W7-R4)', async () => {
    mockFetchAlbums.mockResolvedValue(NO_ALBUMS)
    const wrapper = mount(GalleryView)
    await flushPromises()

    expect(wrapper.find('.ds-band-hero').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Missing photographs')
    expect(mockFetchArchiveCoverage).not.toHaveBeenCalled()
  })

  it("shows the square's own band words, and no coverage list unless chosen", async () => {
    mockFetchAlbums.mockResolvedValue(NO_ALBUMS)
    mockHomeContent.mockResolvedValue(fillHomeContent({ gallery_band: { eyebrow: 'Help', title: 'Old photos?', text: 'Send them in.', button_label: 'Send', show_coverage: false } }))
    const wrapper = mount(GalleryView)
    await flushPromises()

    expect(wrapper.find('.ds-band-hero').text()).toContain('Old photos?')
    expect(wrapper.find('.ds-band-hero').text()).toContain('Send them in.')
    expect(wrapper.find('.ds-band-hero').text()).toContain('Send')
    expect(wrapper.text()).not.toContain('2010–2014')
    expect(mockFetchArchiveCoverage).not.toHaveBeenCalled()
  })

  it('leaves out the button when it has no label', async () => {
    mockFetchAlbums.mockResolvedValue(NO_ALBUMS)
    mockHomeContent.mockResolvedValue(fillHomeContent({ gallery_band: { eyebrow: '', title: 'Old photos?', text: '', button_label: '', show_coverage: false } }))
    const wrapper = mount(GalleryView)
    await flushPromises()

    expect(wrapper.find('.ds-band-hero a').exists()).toBe(false)
  })

  it('renders the real archive coverage eras with a state badge when the square chose it', async () => {
    mockFetchAlbums.mockResolvedValue(NO_ALBUMS)
    mockFetchArchiveCoverage.mockResolvedValue(ERAS)
    mockHomeContent.mockResolvedValue(fillHomeContent({ gallery_band: { eyebrow: '', title: 'Old photos?', text: '', button_label: '', show_coverage: true } }))
    const wrapper = mount(GalleryView)
    await flushPromises()

    expect(wrapper.text()).toContain('2010–2014')
    expect(wrapper.text()).toContain('No photos')
    expect(wrapper.text()).toContain('Complete')
  })

  it('shows a Draft pill only on albums the API marks as unpublished (admin preview)', async () => {
    mockFetchAlbums.mockResolvedValue({
      items: [
        { id: 1, title: 'Live', description: null, category: null, cover_thumbnail_url: null, photo_count: 1, published: true },
        { id: 2, title: 'Hidden', description: null, category: null, cover_thumbnail_url: null, photo_count: 1, published: false },
      ],
      page: 1, per_page: 12, total: 2, total_pages: 1,
    })
    const wrapper = mount(GalleryView)
    await flushPromises()

    expect(wrapper.findAll('.draft-pill')).toHaveLength(1)
  })
})
