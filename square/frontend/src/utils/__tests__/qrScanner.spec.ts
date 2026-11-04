// Tests for qrScanner (7 cases), e.g. createQrScanner; constructs a QrScanner against the given video element and forwards de; start() and stop() delegate to the underlying QrScanner instance.
import { describe, it, expect, vi } from 'vitest'

const mockStart = vi.fn().mockResolvedValue(undefined)
const mockStop = vi.fn()
const mockPause = vi.fn().mockResolvedValue(true)
const mockSetCamera = vi.fn().mockResolvedValue(undefined)
const mockListCameras = vi.fn().mockResolvedValue([{ id: 'cam-1', label: 'Built-in camera' }])
const mockConstructor = vi.fn()

vi.mock('qr-scanner', () => {
  class FakeQrScanner {
    static listCameras(...args: unknown[]) {
      return mockListCameras(...args)
    }
    constructor(...args: unknown[]) {
      mockConstructor(...args)
    }
    start = mockStart
    stop = mockStop
    pause = mockPause
    setCamera = mockSetCamera
  }
  return { default: FakeQrScanner }
})

import { createQrScanner } from '../qrScanner'

describe('createQrScanner', () => {
  it('constructs a QrScanner against the given video element and forwards decoded text', () => {
    const video = document.createElement('video')
    const onDecode = vi.fn()

    createQrScanner(video, onDecode)

    expect(mockConstructor).toHaveBeenCalledTimes(1)
    const [passedVideo, resultCallback] = mockConstructor.mock.calls[0]
    expect(passedVideo).toBe(video)

    resultCallback({ data: 'abc123' })
    expect(onDecode).toHaveBeenCalledWith('abc123')
  })

  it('start() and stop() delegate to the underlying QrScanner instance', async () => {
    const handle = createQrScanner(document.createElement('video'), vi.fn())

    await handle.start()
    handle.stop()

    expect(mockStart).toHaveBeenCalledTimes(1)
    expect(mockStop).toHaveBeenCalledTimes(1)
  })

  it('pause() delegates to the underlying QrScanner instance without stopping the stream', () => {
    const handle = createQrScanner(document.createElement('video'), vi.fn())

    handle.pause()

    expect(mockPause).toHaveBeenCalledTimes(1)
    // No stopStreamImmediately arg — keeps the camera preview visible, only halts decoding.
    expect(mockPause).toHaveBeenCalledWith()
  })

  it('resumes decoding by calling start() again after a pause (per qr-scanner\'s own API)', async () => {
    const handle = createQrScanner(document.createElement('video'), vi.fn())

    handle.pause()
    await handle.start()

    expect(mockPause).toHaveBeenCalledTimes(1)
    expect(mockStart).toHaveBeenCalledTimes(1)
  })

  it('listCameras() requests labelled devices from the underlying QrScanner class', async () => {
    const handle = createQrScanner(document.createElement('video'), vi.fn())

    const cameras = await handle.listCameras()

    expect(mockListCameras).toHaveBeenCalledWith(true)
    expect(cameras).toEqual([{ id: 'cam-1', label: 'Built-in camera' }])
  })

  it('setCamera() delegates to the underlying QrScanner instance', async () => {
    const handle = createQrScanner(document.createElement('video'), vi.fn())

    await handle.setCamera('cam-2')

    expect(mockSetCamera).toHaveBeenCalledWith('cam-2')
  })
})
