// Tests for AdminGalleryDetailView (12 cases), e.g. AdminGalleryDetailView; shows a back link to the gallery list; shows the album form once loaded.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chooseOption, selectedLabel } from '../../../test-utils/baseSelect'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

const mockFetchAdminAlbum = vi.fn()
const mockCreateAdminAlbum = vi.fn()
const mockUpdateAdminAlbum = vi.fn()
const mockUploadMedia = vi.fn()
const mockUpdateMediaCaption = vi.fn()
const mockDeleteMedia = vi.fn()
const mockFetchAdminEvents = vi.fn()

vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: vi.fn().mockResolvedValue([
    { value: 'festivals', label: 'Festivals' },
    { value: 'community', label: 'Community' },
    { value: 'archive', label: 'Archive' },
  ]),
}))

vi.mock('../../../services/adminGalleryApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminGalleryApi')>(
    '../../../services/adminGalleryApi',
  )
  return {
    ...actual,
    fetchAdminAlbum: (...args: unknown[]) => mockFetchAdminAlbum(...args),
    createAdminAlbum: (...args: unknown[]) => mockCreateAdminAlbum(...args),
    updateAdminAlbum: (...args: unknown[]) => mockUpdateAdminAlbum(...args),
    uploadMedia: (...args: unknown[]) => mockUploadMedia(...args),
    updateMediaCaption: (...args: unknown[]) => mockUpdateMediaCaption(...args),
    deleteMedia: (...args: unknown[]) => mockDeleteMedia(...args),
  }
})

vi.mock('../../../services/adminEventsApi', () => ({
  fetchAdminEvents: (...args: unknown[]) => mockFetchAdminEvents(...args),
}))

import AdminGalleryDetailView from '../AdminGalleryDetailView.vue'

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/gallery/new', component: AdminGalleryDetailView },
      { path: '/admin/gallery/:id', component: AdminGalleryDetailView },
      { path: '/admin/gallery', component: { template: '<div />' } },
    ],
  })
  router.push(path)
  await router.isReady()
  return mount(AdminGalleryDetailView, { global: { plugins: [router] } })
}

const baseAlbum = {
  id: 1,
  title: 'Durga Puja 2026',
  description: null,
  event_id: null,
  year: 2026,
  published: false,
  created_at: '',
  updated_at: '',
  media: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAdminEvents.mockResolvedValue({ items: [], page: 1, per_page: 50, total: 0, total_pages: 0 })
})

describe('AdminGalleryDetailView', () => {
  it('shows a back link to the gallery list', async () => {
    mockFetchAdminAlbum.mockResolvedValue(baseAlbum)

    const wrapper = await mountAt('/admin/gallery/1')
    await flushPromises()

    expect(wrapper.find('a[href="/admin/gallery"]').exists()).toBe(true)
  })

  it('shows the album form once loaded', async () => {
    mockFetchAdminAlbum.mockResolvedValue(baseAlbum)

    const wrapper = await mountAt('/admin/gallery/1')
    await flushPromises()

    expect((wrapper.find('input').element as HTMLInputElement).value).toBe('Durga Puja 2026')
  })

  it('saves an edited album', async () => {
    mockFetchAdminAlbum.mockResolvedValue(baseAlbum)
    mockUpdateAdminAlbum.mockResolvedValue({ ...baseAlbum, title: 'Durga Puja 2027' })

    const wrapper = await mountAt('/admin/gallery/1')
    await flushPromises()

    await wrapper.find('input').setValue('Durga Puja 2027')
    await wrapper.find('button.save-album').trigger('click')
    await flushPromises()

    expect(mockUpdateAdminAlbum).toHaveBeenCalledWith(1, expect.objectContaining({ title: 'Durga Puja 2027' }))
  })

 it('sends a blank year as null so the backend rejects it', async () => {
    mockFetchAdminAlbum.mockResolvedValue(baseAlbum)
    mockUpdateAdminAlbum.mockResolvedValue(baseAlbum)
    const wrapper = await mountAt('/admin/gallery/1')
    await flushPromises()

    await wrapper.find('input.year-input').setValue('')
    await wrapper.find('button.save-album').trigger('click')
    await flushPromises()

    expect(mockUpdateAdminAlbum).toHaveBeenCalledWith(1, expect.objectContaining({ year: null }))
  })

  it('pre-fills the category select and saves a changed category', async () => {
    mockFetchAdminAlbum.mockResolvedValue({ ...baseAlbum, category: 'community' })
    mockUpdateAdminAlbum.mockResolvedValue({ ...baseAlbum, category: 'festivals' })

    const wrapper = await mountAt('/admin/gallery/1')
    await flushPromises()

    const last = wrapper.findAll('.base-select').length - 1
    expect(selectedLabel(wrapper, last)).toBe('Community')

    await chooseOption(wrapper, 'festivals', last)
    await wrapper.find('button.save-album').trigger('click')
    await flushPromises()

    expect(mockUpdateAdminAlbum).toHaveBeenCalledWith(1, expect.objectContaining({ category: 'festivals' }))
  })

  it('shows an empty state when the album has no photos yet', async () => {
    mockFetchAdminAlbum.mockResolvedValue(baseAlbum)

    const wrapper = await mountAt('/admin/gallery/1')
    await flushPromises()

    expect(wrapper.text()).toContain('No photos yet')
  })

  it('lists existing media with a delete action', async () => {
    mockFetchAdminAlbum.mockResolvedValue({
      ...baseAlbum,
      media: [{ id: 1, filename: 'a.jpg', url: 'https://x/a.jpg', thumbnail_url: 'https://x/a-thumb.jpg', width: 800, height: 600 }],
    })
    mockDeleteMedia.mockResolvedValue(undefined)

    const wrapper = await mountAt('/admin/gallery/1')
    await flushPromises()

    expect(wrapper.findAll('img')).toHaveLength(1)

    await wrapper.find('button[aria-label="Delete a.jpg"]').trigger('click')
    await flushPromises()

    expect(mockDeleteMedia).toHaveBeenCalledWith(1)
  })

  it('saves a caption typed under a photo', async () => {
    mockFetchAdminAlbum.mockResolvedValue({
      ...baseAlbum,
      media: [{ id: 1, filename: 'a.jpg', url: 'https://x/a.jpg', thumbnail_url: 'https://x/a-thumb.jpg', width: 800, height: 600, caption: null }],
    })
    mockUpdateMediaCaption.mockResolvedValue({ id: 1, caption: 'Cultural programme' })

    const wrapper = await mountAt('/admin/gallery/1')
    await flushPromises()

    const captionInput = wrapper.find('input[placeholder="Add a caption…"]')
    await captionInput.setValue('Cultural programme')
    await captionInput.trigger('change')
    await flushPromises()

    expect(mockUpdateMediaCaption).toHaveBeenCalledWith(1, 'Cultural programme')
  })

  it('uploads selected files and reports per-file errors', async () => {
    mockFetchAdminAlbum.mockResolvedValue(baseAlbum)
    mockUploadMedia.mockResolvedValue({
      created: [{ id: 2, filename: 'good.jpg', url: 'https://x/good.jpg', thumbnail_url: 'https://x/good-thumb.jpg', width: 800, height: 600 }],
      errors: [{ filename: 'bad.jpg', error: 'Not a valid image file.' }],
    })

    const wrapper = await mountAt('/admin/gallery/1')
    await flushPromises()

    const file = new File(['data'], 'good.jpg', { type: 'image/jpeg' })
    const fileInput = wrapper.find('input[type="file"]')
    Object.defineProperty(fileInput.element, 'files', { value: [file] })
    await fileInput.trigger('change')
    await flushPromises()

    expect(mockUploadMedia).toHaveBeenCalledWith(1, [file])
    expect(wrapper.text()).toContain('Not a valid image file.')
  })

  it('uploads photos one request at a time and lists which ones failed and why, with a retry', async () => {
    mockFetchAdminAlbum.mockResolvedValue(baseAlbum)
    const ok = { created: [{ id: 2, filename: 'a.jpg', url: 'u', thumbnail_url: 't', width: 1, height: 1 }], errors: [] }
    mockUploadMedia
      .mockResolvedValueOnce(ok)
      .mockRejectedValueOnce(new Error('The file is too large for the server.'))
      .mockResolvedValueOnce(ok)

    const wrapper = await mountAt('/admin/gallery/1')
    await flushPromises()

    const files = ['a.jpg', 'b.jpg', 'c.jpg'].map((n) => new File(['d'], n, { type: 'image/jpeg' }))
    const fileInput = wrapper.find('input[type="file"]')
    Object.defineProperty(fileInput.element, 'files', { value: files })
    await fileInput.trigger('change')
    await flushPromises()

    expect(mockUploadMedia).toHaveBeenCalledTimes(3)
    expect(mockUploadMedia).toHaveBeenNthCalledWith(2, 1, [files[1]])
    expect(wrapper.text()).toContain('b.jpg: The file is too large for the server.')
    expect(wrapper.text()).toContain('Retry 1 failed')

    mockUploadMedia.mockResolvedValueOnce(ok)
    const retry = wrapper.findAll('button').find((b) => b.text().startsWith('Retry'))
    await retry!.trigger('click')
    await flushPromises()

    expect(mockUploadMedia).toHaveBeenLastCalledWith(1, [files[1]])
    expect(wrapper.text()).not.toContain('Retry')
  })

  it('shows the Photos section after creating a new album, without remounting (reproduction)', async () => {
    mockCreateAdminAlbum.mockResolvedValue({ ...baseAlbum, id: 2, title: 'New Album' })
    mockFetchAdminAlbum.mockResolvedValue({ ...baseAlbum, id: 2, title: 'New Album' })

    const wrapper = await mountAt('/admin/gallery/new')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Photos')

    await wrapper.find('input').setValue('New Album')
    await wrapper.find('button.save-album').trigger('click')
    await flushPromises()

    expect(mockCreateAdminAlbum).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Photos')
  })
})
