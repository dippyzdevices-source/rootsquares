// Tests for AdminNewsFormView (12 cases), e.g. AdminNewsFormView; shows who created and last edited the article when editing; has no slug field (generated server-side).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chooseOption } from '../../../test-utils/baseSelect'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent } from 'vue'

const mockFetchAdminNewsArticle = vi.fn()
const mockCreateAdminNews = vi.fn()
const mockUpdateAdminNews = vi.fn()
const mockUploadNewsBanner = vi.fn()
const mockAddNewsImage = vi.fn()
const mockDeleteNewsImage = vi.fn()

vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: vi.fn().mockResolvedValue([
    { value: 'announcement', label: 'Announcement' },
    { value: 'story', label: 'Story' },
    { value: 'blog', label: 'Blog' },
  ]),
}))

vi.mock('../../../services/adminNewsApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminNewsApi')>(
    '../../../services/adminNewsApi',
  )
  return {
    ...actual,
    fetchAdminNewsArticle: (...args: unknown[]) => mockFetchAdminNewsArticle(...args),
    createAdminNews: (...args: unknown[]) => mockCreateAdminNews(...args),
    updateAdminNews: (...args: unknown[]) => mockUpdateAdminNews(...args),
    uploadNewsBanner: (...args: unknown[]) => mockUploadNewsBanner(...args),
    addNewsImage: (...args: unknown[]) => mockAddNewsImage(...args),
    deleteNewsImage: (...args: unknown[]) => mockDeleteNewsImage(...args),
  }
})

const mockPush = vi.fn()
const routeParams: { id?: string } = {}
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: routeParams }),
  useRouter: () => ({ push: mockPush }),
}))

// Real Tiptap needs a live DOM contenteditable and its own dedicated tests (see
// RichTextEditor.spec.ts) — stubbed here as a plain textarea so this file can test
// AdminNewsFormView's own v-model wiring and save/validation logic in isolation.
vi.mock('../../../components/ui/RichTextEditor.vue', () => ({
  default: defineComponent({
    props: ['modelValue', 'label'],
    emits: ['update:modelValue'],
    template: '<textarea :value="modelValue" @input="onInput" />',
    methods: {
      onInput(event: Event) {
        this.$emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
      },
    },
  }),
}))

import AdminNewsFormView from '../AdminNewsFormView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  delete routeParams.id
})

describe('AdminNewsFormView', () => {
  it('shows who created and last edited the article when editing', async () => {
    routeParams.id = '1'
    mockFetchAdminNewsArticle.mockResolvedValue({
      id: 1, title: 'Existing', slug: 'existing', summary: null, content: 'Body', banner_image: null,
      status: 'draft', category: null, published_at: null,
      created_by_email: 'creator@example.com', updated_by_email: 'editor@example.com',
      created_at: '', updated_at: '',
    })

    const wrapper = mount(AdminNewsFormView)
    await flushPromises()

    expect(wrapper.text()).toContain('Created by creator@example.com')
    expect(wrapper.text()).toContain('Last edited by editor@example.com')
  })

  it('has no slug field (generated server-side)', async () => {
    const wrapper = mount(AdminNewsFormView)
    await flushPromises()
    expect(wrapper.text()).not.toContain('Slug')
  })

  it('creates a new article', async () => {
    mockCreateAdminNews.mockResolvedValue({ id: 1, title: 'New article', slug: 'new-article' })

    const wrapper = mount(AdminNewsFormView)
    await flushPromises()

    await wrapper.find('input[placeholder="Article title"]').setValue('New article')
    await wrapper.findAll('textarea')[1].setValue('Body text.')
    await wrapper.find('button.save-news').trigger('click')
    await flushPromises()

    expect(mockCreateAdminNews).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'New article', content: 'Body text.' }),
    )
  })

  it('creates a new article with a category', async () => {
    mockCreateAdminNews.mockResolvedValue({ id: 1, title: 'New article', slug: 'new-article' })

    const wrapper = mount(AdminNewsFormView)
    await flushPromises()

    await wrapper.find('input[placeholder="Article title"]').setValue('New article')
    await wrapper.findAll('textarea')[1].setValue('Body text.')
    await chooseOption(wrapper, 'story', wrapper.findAll('.base-select-button').length - 1)
    await wrapper.find('button.save-news').trigger('click')
    await flushPromises()

    expect(mockCreateAdminNews).toHaveBeenCalledWith(
      expect.objectContaining({ category: 'story' }),
    )
  })

  it('shows validation errors from the API', async () => {
    const { ValidationError } = await vi.importActual<typeof import('../../../services/adminNewsApi')>(
      '../../../services/adminNewsApi',
    )
    mockCreateAdminNews.mockRejectedValue(new ValidationError({ title: 'This field is required.' }))

    const wrapper = mount(AdminNewsFormView)
    await flushPromises()

    await wrapper.find('button.save-news').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('This field is required.')
  })

  it('shows a summary length error from the API', async () => {
    const { ValidationError } = await vi.importActual<typeof import('../../../services/adminNewsApi')>(
      '../../../services/adminNewsApi',
    )
    mockCreateAdminNews.mockRejectedValue(new ValidationError({ summary: 'Must be at most 500 characters.' }))

    const wrapper = mount(AdminNewsFormView)
    await flushPromises()
    await wrapper.find('button.save-news').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Must be at most 500 characters.')
  })
})

describe('AdminNewsFormView banner upload', () => {
  it('uploads a banner image and shows the preview', async () => {
    routeParams.id = '1'
    mockFetchAdminNewsArticle.mockResolvedValue({
      id: 1, title: 'Existing', slug: 'existing', summary: null, content: 'Body', banner_image: null,
      status: 'draft', category: null, published_at: null,
      created_by_email: null, updated_by_email: null, created_at: '', updated_at: '',
    })
    mockUploadNewsBanner.mockResolvedValue({ banner_image: 'https://x/banner.jpg' })

    const wrapper = mount(AdminNewsFormView)
    await flushPromises()

    const file = new File(['data'], 'banner.jpg', { type: 'image/jpeg' })
    const fileInput = wrapper.find('input[type="file"][accept*="image/jpeg"]')
    Object.defineProperty(fileInput.element, 'files', { value: [file] })
    await fileInput.trigger('change')
    await flushPromises()

    expect(mockUploadNewsBanner).toHaveBeenCalledWith(1, file)
    expect(wrapper.find('img[alt="Article banner"]').attributes('src')).toBe('https://x/banner.jpg')
  })

  it('removes the banner image', async () => {
    routeParams.id = '1'
    mockFetchAdminNewsArticle.mockResolvedValue({
      id: 1, title: 'Existing', slug: 'existing', summary: null, content: 'Body',
      banner_image: 'https://x/banner.jpg',
      status: 'draft', category: null, published_at: null,
      created_by_email: null, updated_by_email: null, created_at: '', updated_at: '',
    })
    mockUpdateAdminNews.mockResolvedValue({ banner_image: null })

    const wrapper = mount(AdminNewsFormView)
    await flushPromises()

    expect(wrapper.find('img[alt="Article banner"]').exists()).toBe(true)

    await wrapper.findAll('button').find((b) => b.text() === 'Remove')!.trigger('click')
    await flushPromises()

    expect(mockUpdateAdminNews).toHaveBeenCalledWith(1, { banner_image: null })
    expect(wrapper.find('img[alt="Article banner"]').exists()).toBe(false)
  })

  it('adds an image to the gallery without touching the lead banner_image', async () => {
    routeParams.id = '1'
    mockFetchAdminNewsArticle.mockResolvedValue({
      id: 1, title: 'Existing', slug: 'existing', summary: null, content: 'Body', banner_image: null,
      images: [], status: 'draft', category: null, published_at: null,
      created_by_email: null, updated_by_email: null, created_at: '', updated_at: '',
    })
    mockAddNewsImage.mockResolvedValue({
      images: [{ id: 1, image_url: 'https://x/photo-one.jpg', sort_order: 0 }],
    })

    const wrapper = mount(AdminNewsFormView)
    await flushPromises()

    const file = new File(['data'], 'photo-one.jpg', { type: 'image/jpeg' })
    const fileInputs = wrapper.findAll('input[type="file"][accept*="image/jpeg"]')
    Object.defineProperty(fileInputs[1].element, 'files', { value: [file] })
    await fileInputs[1].trigger('change')
    await flushPromises()

    expect(mockAddNewsImage).toHaveBeenCalledWith(1, file)
    expect(wrapper.find('img[alt="Article image"]').attributes('src')).toBe('https://x/photo-one.jpg')
  })

  it('removes an image from the gallery', async () => {
    routeParams.id = '1'
    mockFetchAdminNewsArticle.mockResolvedValue({
      id: 1, title: 'Existing', slug: 'existing', summary: null, content: 'Body', banner_image: null,
      images: [{ id: 1, image_url: 'https://x/photo-one.jpg', sort_order: 0 }],
      status: 'draft', category: null, published_at: null,
      created_by_email: null, updated_by_email: null, created_at: '', updated_at: '',
    })
    mockDeleteNewsImage.mockResolvedValue({ images: [] })

    const wrapper = mount(AdminNewsFormView)
    await flushPromises()

    expect(wrapper.find('img[alt="Article image"]').exists()).toBe(true)

    await wrapper.find('button[aria-label="Remove this image"]').trigger('click')
    await flushPromises()

    expect(mockDeleteNewsImage).toHaveBeenCalledWith(1, 1)
    expect(wrapper.find('img[alt="Article image"]').exists()).toBe(false)
  })
})
