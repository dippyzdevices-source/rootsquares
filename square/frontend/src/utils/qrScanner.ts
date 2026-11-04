import QrScanner from 'qr-scanner'

export interface CameraOption {
  id: string
  label: string
}

export interface QrScannerHandle {
  start(): Promise<void>
  stop(): void
  // Stops decoding without tearing down the camera stream, so the preview stays visible with
  // no flicker — used while a scan result panel is on screen. Resume by calling start() again.
  pause(): void
  // Camera labels are only populated once permission has been granted — call this after
  // start() has succeeded, not before.
  listCameras(): Promise<CameraOption[]>
  setCamera(cameraId: string): Promise<void>
}

// The only file in this project that touches the qr-scanner library directly — every consumer
// (CheckinScanView.vue) imports this instead, and every test mocks this module wholesale
// rather than dealing with qr-scanner's camera/worker internals under jsdom.
export function createQrScanner(
  videoElement: HTMLVideoElement,
  onDecode: (code: string) => void,
): QrScannerHandle {
  const scanner = new QrScanner(videoElement, (result) => onDecode(result.data), {
    highlightScanRegion: true,
    highlightCodeOutline: true,
  })

  return {
    start: () => scanner.start(),
    stop: () => scanner.stop(),
    pause: () => {
      void scanner.pause()
    },
    listCameras: () => QrScanner.listCameras(true),
    setCamera: (cameraId: string) => scanner.setCamera(cameraId),
  }
}
