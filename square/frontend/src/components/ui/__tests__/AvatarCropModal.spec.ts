// Tests for AvatarCropModal (6 cases), e.g. AvatarCropModal; shows the crop UI when open with a file; cancel closes the modal without emitting a cropped image.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, DOMWrapper } from '@vue/test-utils'
import AvatarCropModal from '../AvatarCropModal.vue'

function mountModal(file: File | null = new File(['bytes'], 'photo.jpg', { type: 'image/jpeg' })) {
  return mount(AvatarCropModal, {
    props: { modelValue: true, file },
  })
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('AvatarCropModal', () => {
  it('shows the crop UI when open with a file', () => {
    const wrapper = mountModal()
    const body = new DOMWrapper(document.body)

    expect(body.text()).toContain('Crop your photo')
    expect(body.find('input[type="range"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('cancel closes the modal without emitting a cropped image', async () => {
    const wrapper = mountModal()
    const body = new DOMWrapper(document.body)

    await body.findAll('button').find((b) => b.text() === 'Cancel')!.trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
    expect(wrapper.emitted('cropped')).toBeUndefined()

    wrapper.unmount()
  })

  it('disables Save until the image has loaded', () => {
    const wrapper = mountModal()
    const body = new DOMWrapper(document.body)

    const saveButton = body.findAll('button').find((b) => b.text() === 'Save photo')!
    expect((saveButton.element as HTMLButtonElement).disabled).toBe(true)

    wrapper.unmount()
  })

  it('emits a cropped blob when Save is clicked after the image loads', async () => {
    const drawImage = vi.fn()
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D)
    const fakeBlob = new Blob(['cropped'], { type: 'image/jpeg' })
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((callback) => {
      callback(fakeBlob)
    })

    const wrapper = mountModal()
    const body = new DOMWrapper(document.body)

    const img = body.find('img')
    Object.defineProperty(img.element, 'naturalWidth', { value: 800, configurable: true })
    Object.defineProperty(img.element, 'naturalHeight', { value: 600, configurable: true })
    await img.trigger('load')

    const saveButton = body.findAll('button').find((b) => b.text() === 'Save photo')!
    expect((saveButton.element as HTMLButtonElement).disabled).toBe(false)
    await saveButton.trigger('click')

    expect(drawImage).toHaveBeenCalled()
    expect(wrapper.emitted('cropped')?.[0]).toEqual([fakeBlob])

    wrapper.unmount()
    vi.restoreAllMocks()
  })

  it('resets the loaded state when given a new file', async () => {
    const wrapper = mountModal()
    const body = new DOMWrapper(document.body)

    const img = body.find('img')
    Object.defineProperty(img.element, 'naturalWidth', { value: 800, configurable: true })
    Object.defineProperty(img.element, 'naturalHeight', { value: 600, configurable: true })
    await img.trigger('load')

    let saveButton = body.findAll('button').find((b) => b.text() === 'Save photo')!
    expect((saveButton.element as HTMLButtonElement).disabled).toBe(false)

    await wrapper.setProps({ file: new File(['other'], 'other.jpg', { type: 'image/jpeg' }) })

    saveButton = body.findAll('button').find((b) => b.text() === 'Save photo')!
    expect((saveButton.element as HTMLButtonElement).disabled).toBe(true)

    wrapper.unmount()
  })
})
