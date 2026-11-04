// Tests for AdminCommitteeFormView (7 cases), e.g. AdminCommitteeFormView; creates a new committee member; loads and edits an existing committee member.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chooseOption, selectedLabel } from '../../../test-utils/baseSelect'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

const mockFetchAdminCommitteeMember = vi.fn()
const mockCreateAdminCommitteeMember = vi.fn()
const mockUpdateAdminCommitteeMember = vi.fn()
const mockUploadAdminCommitteePhoto = vi.fn()

vi.mock('../../../services/lookupsApi', () => ({
  fetchLookup: vi.fn().mockResolvedValue([
    { value: 'president', label: 'President' },
    { value: 'vice_president', label: 'Vice President' },
    { value: 'general_secretary', label: 'General Secretary' },
    { value: 'treasurer', label: 'Treasurer' },
    { value: 'advisor', label: 'Advisor' }
  ]),
}))

vi.mock('../../../services/adminCommitteeApi', async () => {
  const actual = await vi.importActual<typeof import('../../../services/adminCommitteeApi')>(
    '../../../services/adminCommitteeApi',
  )
  return {
    ...actual,
    fetchAdminCommitteeMember: (...args: unknown[]) => mockFetchAdminCommitteeMember(...args),
    createAdminCommitteeMember: (...args: unknown[]) => mockCreateAdminCommitteeMember(...args),
    updateAdminCommitteeMember: (...args: unknown[]) => mockUpdateAdminCommitteeMember(...args),
    uploadAdminCommitteePhoto: (...args: unknown[]) => mockUploadAdminCommitteePhoto(...args),
  }
})

import AdminCommitteeFormView from '../AdminCommitteeFormView.vue'

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/content/committee/new', component: AdminCommitteeFormView },
      { path: '/admin/content/committee/:id/edit', component: AdminCommitteeFormView },
    ],
  })
  router.push(path)
  await router.isReady()
  return mount(AdminCommitteeFormView, { global: { plugins: [router], stubs: { RouterLink: true } } })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AdminCommitteeFormView', () => {
  it('creates a new committee member', async () => {
    mockCreateAdminCommitteeMember.mockResolvedValue({
      id: 1, name: 'Priya Das', role: 'President', portrait_url: null, address: null,
      email: null, phone: null, member_since: null,
      quote: null, display_order: 0, is_active: true, created_at: '', updated_at: '',
    })

    const wrapper = await mountAt('/admin/content/committee/new')
    await flushPromises()

    await wrapper.find('input[placeholder="Priya Das"]').setValue('Priya Das')
    await chooseOption(wrapper, 'President')
    await wrapper.find('button.save-committee-member').trigger('click')
    await flushPromises()

    expect(mockCreateAdminCommitteeMember).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Priya Das', role: 'President' }),
    )
  })

  it('loads and edits an existing committee member', async () => {
    mockFetchAdminCommitteeMember.mockResolvedValue({
      id: 1, name: 'Priya Das', role: 'President', portrait_url: null, address: 'Oslo',
      email: 'priya@bcaoslo.no', phone: '+47 401 22 318', member_since: 1994,
      quote: 'Leads the association.', display_order: 2, is_active: true,
      created_at: '', updated_at: '',
    })
    mockUpdateAdminCommitteeMember.mockResolvedValue({
      id: 1, name: 'Priya Das', role: 'Vice President', portrait_url: null, address: 'Oslo',
      email: 'priya@bcaoslo.no', phone: '+47 401 22 318', member_since: 1994,
      quote: 'Leads the association.', display_order: 2, is_active: true,
      created_at: '', updated_at: '',
    })

    const wrapper = await mountAt('/admin/content/committee/1/edit')
    await flushPromises()

    expect(selectedLabel(wrapper)).toBe('President')

    await chooseOption(wrapper, 'Vice President')
    await wrapper.find('button.save-committee-member').trigger('click')
    await flushPromises()

    expect(mockUpdateAdminCommitteeMember).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ role: 'Vice President' }),
    )
  })

  it('shows validation errors from the API', async () => {
    const { ValidationError } = await vi.importActual<typeof import('../../../services/adminCommitteeApi')>(
      '../../../services/adminCommitteeApi',
    )
    mockCreateAdminCommitteeMember.mockRejectedValue(new ValidationError({ name: 'This field is required.' }))

    const wrapper = await mountAt('/admin/content/committee/new')
    await flushPromises()

    await wrapper.find('button.save-committee-member').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('This field is required.')
  })

  it('reveals a free-text field for a custom role via "Other"', async () => {
    mockCreateAdminCommitteeMember.mockResolvedValue({
      id: 1, name: 'Priya Das', role: 'Youth Coordinator', portrait_url: null, address: null,
      email: null, phone: null, member_since: null,
      quote: null, display_order: 0, is_active: true, created_at: '', updated_at: '',
    })

    const wrapper = await mountAt('/admin/content/committee/new')
    await flushPromises()

    await wrapper.find('input[placeholder="Priya Das"]').setValue('Priya Das')
    await chooseOption(wrapper, '__other__')
    await wrapper.find('input[placeholder="Enter the exact role"]').setValue('Youth Coordinator')
    await wrapper.find('button.save-committee-member').trigger('click')
    await flushPromises()

    expect(mockCreateAdminCommitteeMember).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Priya Das', role: 'Youth Coordinator' }),
    )
  })

  it('pre-selects "Other" with the existing value when a role is not in the preset list', async () => {
    mockFetchAdminCommitteeMember.mockResolvedValue({
      id: 1, name: 'Priya Das', role: 'Youth Coordinator', portrait_url: null, address: null,
      email: null, phone: null, member_since: null,
      quote: null, display_order: 0, is_active: true, created_at: '', updated_at: '',
    })

    const wrapper = await mountAt('/admin/content/committee/1/edit')
    await flushPromises()

    expect(selectedLabel(wrapper)).toBe('Other')
    expect((wrapper.find('input[placeholder="Enter the exact role"]').element as HTMLInputElement).value).toBe('Youth Coordinator')
  })

  it('opens a crop step (rectangular, not square) before uploading a selected portrait', async () => {
    mockFetchAdminCommitteeMember.mockResolvedValue({
      id: 1, name: 'Priya Das', role: 'President', portrait_url: null, address: null,
      email: null, phone: null, member_since: null,
      quote: null, display_order: 0, is_active: true, created_at: '', updated_at: '',
    })
    mockUploadAdminCommitteePhoto.mockResolvedValue({
      id: 1, name: 'Priya Das', role: 'President', portrait_url: 'https://cdn.example.com/portrait.jpg',
      address: null, email: null, phone: null, member_since: null,
      quote: null, display_order: 0, is_active: true, created_at: '', updated_at: '',
    })

    const drawImage = vi.fn()
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D)
    const fakeBlob = new Blob(['cropped'], { type: 'image/jpeg' })
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((callback) => {
      callback(fakeBlob)
    })

    const wrapper = await mountAt('/admin/content/committee/1/edit')
    await flushPromises()

    const file = new File(['image-bytes'], 'portrait.jpg', { type: 'image/jpeg' })
    const fileInput = wrapper.find('input[type="file"]')
    Object.defineProperty(fileInput.element, 'files', { value: [file] })
    await fileInput.trigger('change')
    await flushPromises()

    const body = new DOMWrapper(document.body)
    expect(body.text()).toContain('Crop your photo')
    // A 3:4 aspect ratio, not the default square — the crop viewport's width/height differ.
    const viewportEl = body.find('.ds-crop-viewport').element as HTMLElement
    expect(viewportEl.style.width).not.toBe(viewportEl.style.height)
    expect(mockUploadAdminCommitteePhoto).not.toHaveBeenCalled()

    const img = body.find('img')
    Object.defineProperty(img.element, 'naturalWidth', { value: 800, configurable: true })
    Object.defineProperty(img.element, 'naturalHeight', { value: 600, configurable: true })
    await img.trigger('load')

    await body.findAll('button').find((b) => b.text() === 'Save photo')!.trigger('click')
    await flushPromises()

    expect(mockUploadAdminCommitteePhoto).toHaveBeenCalledTimes(1)
    expect(mockUploadAdminCommitteePhoto.mock.calls[0][0]).toBe(1)
    const uploadedFile = mockUploadAdminCommitteePhoto.mock.calls[0][1] as File
    expect(uploadedFile.type).toBe('image/jpeg')

    vi.restoreAllMocks()
  })
})
