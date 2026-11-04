// Tests for GalleryAlbumView (6 cases), e.g. GalleryAlbumView; shows the album title and photo grid once loaded; opens a lightbox with the full-size image when a photo is clicked.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'

const mockFetchAlbum = vi.fn()

vi.mock('../../../services/galleryApi', () => ({
  fetchAlbum: (...args: unknown[]) => mockFetchAlbum(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
}))

import GalleryAlbumView from '../GalleryAlbumView.vue'

const baseAlbum = {
  id: 1,
  title: 'Durga Puja 2026',
  description: 'Five days of celebration.',
  event_id: null,
  media: [
    { id: 1, filename: 'a.jpg', url: 'https://x/a.jpg', thumbnail_url: 'https://x/a-thumb.jpg', width: 800, height: 600 },
    { id: 2, filename: 'b.jpg', url: 'https://x/b.jpg', thumbnail_url: 'https://x/b-thumb.jpg', width: 800, height: 600 },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('GalleryAlbumView', () => {
  it('shows the album title and photo grid once loaded', async () => {
    mockFetchAlbum.mockResolvedValue(baseAlbum)

    const wrapper = mount(GalleryAlbumView)
    await flushPromises()

    expect(wrapper.text()).toContain('Durga Puja 2026')
    expect(wrapper.findAll('img')).toHaveLength(2)
  })

  it('opens a lightbox with the full-size image when a photo is clicked', async () => {
    mockFetchAlbum.mockResolvedValue(baseAlbum)

    const wrapper = mount(GalleryAlbumView)
    await flushPromises()

    await wrapper.findAll('img')[0].trigger('click')

    const body = new DOMWrapper(document.body)
    expect(body.find('img[src="https://x/a.jpg"]').exists()).toBe(true)
    expect(body.find('button[aria-label="Next photo"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('swipes to the next photo on a left swipe, and back on a right swipe', async () => {
    mockFetchAlbum.mockResolvedValue(baseAlbum)

    const wrapper = mount(GalleryAlbumView)
    await flushPromises()

    await wrapper.findAll('img')[0].trigger('click')
    const body = new DOMWrapper(document.body)
    const lightboxImage = () => body.find('img[alt="a.jpg"], img[alt="b.jpg"]')

    await lightboxImage().trigger('touchstart', { touches: [{ clientX: 200 }] })
    await lightboxImage().trigger('touchend', { changedTouches: [{ clientX: 100 }] })
    expect(body.find('img[src="https://x/b.jpg"]').exists()).toBe(true)

    await lightboxImage().trigger('touchstart', { touches: [{ clientX: 100 }] })
    await lightboxImage().trigger('touchend', { changedTouches: [{ clientX: 200 }] })
    expect(body.find('img[src="https://x/a.jpg"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('shows a photo caption in the lightbox when one is set', async () => {
    mockFetchAlbum.mockResolvedValue({
      ...baseAlbum,
      media: [{ ...baseAlbum.media[0], caption: 'Cultural programme, Friday evening' }],
    })

    const wrapper = mount(GalleryAlbumView)
    await flushPromises()

    await wrapper.findAll('img')[0].trigger('click')

    const body = new DOMWrapper(document.body)
    expect(body.text()).toContain('Cultural programme, Friday evening')

    wrapper.unmount()
  })

  it('shows a not-found state on a 404', async () => {
    mockFetchAlbum.mockRejectedValue(new Error('Failed to fetch album: 404'))

    const wrapper = mount(GalleryAlbumView)
    await flushPromises()

    expect(wrapper.text()).toContain('not found')
  })
})
