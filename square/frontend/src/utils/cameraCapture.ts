// The only file that touches getUserMedia/canvas snapshotting directly for the receipt
// camera capture feature — mirrors qrScanner.ts's own "one wrapper module, mock it wholesale
// in tests" convention, since jsdom has no real camera/canvas pixel support to test against.
export interface CameraOption {
  id: string
  label: string
}

export interface CameraCaptureHandle {
  start(): Promise<void>
  stop(): void
  capture(fileName?: string): Promise<File>
  // Camera labels are only populated once permission has been granted — call this after
  // start() has succeeded, not before (same rule as qrScanner.ts's own listCameras()).
  listCameras(): Promise<CameraOption[]>
  setCamera(deviceId: string): Promise<void>
}

export function createCameraCapture(videoElement: HTMLVideoElement): CameraCaptureHandle {
  let stream: MediaStream | null = null

  async function openStream(deviceId?: string) {
    stream?.getTracks().forEach((track) => track.stop())
    stream = await navigator.mediaDevices.getUserMedia({
      video: deviceId ? { deviceId: { exact: deviceId } } : { facingMode: 'environment' },
      audio: false,
    })
    videoElement.srcObject = stream
    await videoElement.play()
  }

  return {
    start: () => openStream(),

    stop() {
      stream?.getTracks().forEach((track) => track.stop())
      stream = null
      videoElement.srcObject = null
    },

    async capture(fileName = 'receipt.jpg') {
      const canvas = document.createElement('canvas')
      canvas.width = videoElement.videoWidth
      canvas.height = videoElement.videoHeight
      const context = canvas.getContext('2d')
      if (!context) throw new Error('Canvas is not supported in this browser.')
      context.drawImage(videoElement, 0, 0, canvas.width, canvas.height)

      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
      if (!blob) throw new Error('Could not capture a photo.')
      return new File([blob], fileName, { type: 'image/jpeg' })
    },

    async listCameras() {
      const devices = await navigator.mediaDevices.enumerateDevices()
      return devices
        .filter((device) => device.kind === 'videoinput')
        .map((device, index) => ({ id: device.deviceId, label: device.label || `Camera ${index + 1}` }))
    },

    setCamera: (deviceId: string) => openStream(deviceId),
  }
}
