// Tests for MemberSettingsView (6 cases), e.g. MemberSettingsView; shows the profile once loaded; pre-fills the name field from the Google account when the member has n.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../../../stores/auth'
import type { Session } from '@supabase/supabase-js'

const mockFetchMyMember = vi.fn()
const mockSaveMyMember = vi.fn()
const mockExportMyData = vi.fn()
const mockUploadMyPhoto = vi.fn()

vi.mock('../../../services/memberApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/memberApi')>(
    '../../../services/memberApi',
  )
  return {
    ...actual,
    fetchMyMember: (...args: unknown[]) => mockFetchMyMember(...args),
    saveMyMember: (...args: unknown[]) => mockSaveMyMember(...args),
    uploadMyPhoto: (...args: unknown[]) => mockUploadMyPhoto(...args),
    exportMyData: (...args: unknown[]) => mockExportMyData(...args),
  }
})

vi.mock('../../../services/supabaseClient', () => ({
  supabase: { auth: { signOut: vi.fn().mockResolvedValue({ error: null }) } },
}))

import MemberSettingsView from '../MemberSettingsView.vue'

function mountView() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/', component: { template: '<div/>' } }],
  })
  return mount(MemberSettingsView, { global: { plugins: [router] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MemberSettingsView', () => {
  it('shows the profile once loaded', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: 'Oslo, Norway', photo_url: null, family_info: null })

    const wrapper = mountView()
    await flushPromises()

    expect((wrapper.find('input[type="text"]').element as HTMLInputElement).value).toBe('Priya Das')
  })

  it('pre-fills the name field from the Google account when the member has none yet', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: '', address: null, photo_url: null, family_info: null })
    const authStore = useAuthStore()
    authStore.session = {
      access_token: 'token-123',
      user: { user_metadata: { full_name: 'Priya Das' } },
    } as unknown as Session

    const wrapper = mountView()
    await flushPromises()

    expect((wrapper.find('input[type="text"]').element as HTMLInputElement).value).toBe('Priya Das')
  })

  it('saves the profile', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, photo_url: null, family_info: null })
    mockSaveMyMember.mockResolvedValue({ id: 1, name: 'Priya D.', address: null, photo_url: null, family_info: null })

    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAll('input[type="text"]')[0].setValue('Priya D.')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(mockSaveMyMember).toHaveBeenCalledWith({ name: 'Priya D.', phone: null, address: null })
  })

  it('opens a crop step before uploading a selected photo', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, photo_url: null, family_info: null })
    mockUploadMyPhoto.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, photo_url: 'https://cdn.example.com/photo.jpg', family_info: null })

    const drawImage = vi.fn()
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D)
    const fakeBlob = new Blob(['cropped'], { type: 'image/jpeg' })
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((callback) => {
      callback(fakeBlob)
    })

    const wrapper = mountView()
    await flushPromises()

    const file = new File(['image-bytes'], 'photo.jpg', { type: 'image/jpeg' })
    const fileInput = wrapper.find('input[type="file"]')
    Object.defineProperty(fileInput.element, 'files', { value: [file] })
    await fileInput.trigger('change')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    expect(body.text()).toContain('Crop your photo')
    // Uploading only happens once the crop is confirmed, never on bare file selection.
    expect(mockUploadMyPhoto).not.toHaveBeenCalled()

    const img = body.find('img')
    Object.defineProperty(img.element, 'naturalWidth', { value: 800, configurable: true })
    Object.defineProperty(img.element, 'naturalHeight', { value: 600, configurable: true })
    await img.trigger('load')

    await body.findAll('button').find((b) => b.text() === 'Save photo')!.trigger('click')
    await flushPromises()

    expect(mockUploadMyPhoto).toHaveBeenCalledTimes(1)
    const uploadedFile = mockUploadMyPhoto.mock.calls[0][0] as File
    expect(uploadedFile.type).toBe('image/jpeg')
    expect(wrapper.text()).toContain('Replace photo')

    vi.restoreAllMocks()
  })

  it('exports the member data as a downloaded file', async () => {
    mockFetchMyMember.mockResolvedValue({ id: 1, name: 'Priya Das', address: null, family_info: null })
    mockExportMyData.mockResolvedValue({ account: { email: 'priya@example.com' }, profile: null, memberships: [], orders: [] })

    const createObjectURL = vi.fn().mockReturnValue('blob:mock')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('button.export-my-data').trigger('click')
    await flushPromises()

    expect(mockExportMyData).toHaveBeenCalled()
    expect(createObjectURL).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()

    clickSpy.mockRestore()
    vi.unstubAllGlobals()
  })
})
