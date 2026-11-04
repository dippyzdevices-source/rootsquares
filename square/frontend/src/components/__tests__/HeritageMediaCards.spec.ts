// Tests for HeritageMediaCards (3 cases), e.g. HeritageMediaCards; shows the current image and uploads a replacement; shows a placeholder when nothing has been uploaded yet.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockFetchAdminSettings = vi.fn()
const mockUploadHeritageImage = vi.fn()

vi.mock('../../services/adminSettingsApi', () => ({
  fetchAdminSettings: () => mockFetchAdminSettings(),
  uploadHeritageImage: (...args: unknown[]) => mockUploadHeritageImage(...args),
}))

import HeritageMediaCards from '../HeritageMediaCards.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('HeritageMediaCards', () => {
  it('shows the current image and uploads a replacement', async () => {
    mockFetchAdminSettings.mockResolvedValue({ heritage_image_url: 'https://x/old.jpg' })
    mockUploadHeritageImage.mockResolvedValue({ heritage_image_url: 'https://x/new.jpg' })
    const wrapper = mount(HeritageMediaCards, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('img').attributes('src')).toBe('https://x/old.jpg')

    const file = new File(['x'], 'group.jpg', { type: 'image/jpeg' })
    const input = wrapper.find('input.heritage-image-input')
    Object.defineProperty(input.element, 'files', { value: [file] })
    await input.trigger('change')
    await flushPromises()

    expect(mockUploadHeritageImage).toHaveBeenCalledWith(file)
    expect(wrapper.find('img').attributes('src')).toBe('https://x/new.jpg')
  })

  it('shows a placeholder when nothing has been uploaded yet', async () => {
    mockFetchAdminSettings.mockResolvedValue({ heritage_image_url: null })
    const wrapper = mount(HeritageMediaCards, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('Upload image')
  })
})
