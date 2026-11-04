// Tests for ReceiptCameraModal (7 cases), e.g. ReceiptCameraModal; starts the camera once opened; shows an error and disables Capture if the camera fails to start.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { chooseOption, optionLabels } from '../../../test-utils/baseSelect'
import { mount, flushPromises, DOMWrapper, type VueWrapper } from '@vue/test-utils'

const mockCameraStart = vi.fn()
const mockCameraStop = vi.fn()
const mockCameraCapture = vi.fn()
const mockListCameras = vi.fn().mockResolvedValue([])
const mockSetCamera = vi.fn().mockResolvedValue(undefined)

vi.mock('../../../utils/cameraCapture', () => ({
  createCameraCapture: vi.fn(() => ({
    start: mockCameraStart,
    stop: mockCameraStop,
    capture: mockCameraCapture,
    listCameras: mockListCameras,
    setCamera: mockSetCamera,
  })),
}))

import ReceiptCameraModal from '../ReceiptCameraModal.vue'

let currentWrapper: VueWrapper | null = null

afterEach(() => {
  vi.clearAllMocks()
  currentWrapper?.unmount()
  currentWrapper = null
})

async function mountOpen() {
  const wrapper = mount(ReceiptCameraModal, { props: { modelValue: false } })
  currentWrapper = wrapper
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

describe('ReceiptCameraModal', () => {
  it('starts the camera once opened', async () => {
    mockCameraStart.mockResolvedValue(undefined)

    await mountOpen()

    expect(mockCameraStart).toHaveBeenCalledTimes(1)
  })

  it('shows an error and disables Capture if the camera fails to start', async () => {
    mockCameraStart.mockRejectedValue(new Error('denied'))

    await mountOpen()

    const body = new DOMWrapper(document.body)
    expect(body.text()).toContain("Couldn't access the camera")
    const captureButton = body.findAll('button').find((b) => b.text() === 'Capture')
    expect((captureButton!.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('captures a photo, emits it, and stops the camera', async () => {
    mockCameraStart.mockResolvedValue(undefined)
    const file = new File(['bytes'], 'receipt.jpg', { type: 'image/jpeg' })
    mockCameraCapture.mockResolvedValue(file)

    const wrapper = await mountOpen()
    const body = new DOMWrapper(document.body)

    const captureButton = body.findAll('button').find((b) => b.text() === 'Capture')
    await captureButton!.trigger('click')
    await flushPromises()

    expect(mockCameraCapture).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('captured')).toEqual([[file]])
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    expect(mockCameraStop).toHaveBeenCalled()
  })

  it('stops the camera when cancelled', async () => {
    mockCameraStart.mockResolvedValue(undefined)

    const wrapper = await mountOpen()
    const body = new DOMWrapper(document.body)

    const cancelButton = body.findAll('button').find((b) => b.text() === 'Cancel')
    await cancelButton!.trigger('click')

    expect(mockCameraStop).toHaveBeenCalled()
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('shows no camera picker when only one camera is available', async () => {
    mockCameraStart.mockResolvedValue(undefined)
    mockListCameras.mockResolvedValue([{ id: 'cam-1', label: 'Back camera' }])

    await mountOpen()
    const body = new DOMWrapper(document.body)

    expect(body.find('.base-select').exists()).toBe(false)
  })

  it('shows a camera picker and switches cameras when more than one is available', async () => {
    mockCameraStart.mockResolvedValue(undefined)
    mockListCameras.mockResolvedValue([
      { id: 'cam-1', label: 'Back camera' },
      { id: 'cam-2', label: 'Front camera' },
    ])

    await mountOpen()
    const body = new DOMWrapper(document.body)

    expect(body.find('.base-select').exists()).toBe(true)
    await body.find('.base-select-button').trigger('click')
    expect(optionLabels(body)).toEqual([
      'Default camera',
      'Back camera',
      'Front camera',
    ])

    await chooseOption(body, 'cam-2')
    await flushPromises()

    expect(mockSetCamera).toHaveBeenCalledWith('cam-2')
  })
})
