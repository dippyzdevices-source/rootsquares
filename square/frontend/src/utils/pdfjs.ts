// Lazy loader for pdf.js so its (large) bundle is only fetched on pages that actually show a PDF:
// the reader page and the admin magazine form, never the rest of the site.
import type * as PdfJs from 'pdfjs-dist'

let cached: Promise<typeof PdfJs> | null = null

export function loadPdfJs(): Promise<typeof PdfJs> {
  if (!cached) {
    cached = (async () => {
      const pdfjs = await import('pdfjs-dist')
      const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url')
      pdfjs.GlobalWorkerOptions.workerSrc = worker.default
      return pdfjs
    })()
  }
  return cached
}

/** Renders page 1 of a PDF (file or URL) to a JPEG blob, used to auto-generate a magazine cover. */
export async function renderFirstPageToBlob(source: File | string, targetWidth = 800): Promise<Blob> {
  const pdfjs = await loadPdfJs()
  const params = typeof source === 'string' ? { url: source, disableRange: true, disableStream: true } : { data: new Uint8Array(await source.arrayBuffer()) }
  const task = pdfjs.getDocument(params)
  const doc = await task.promise
  try {
    const page = await doc.getPage(1)
    const base = page.getViewport({ scale: 1 })
    const viewport = page.getViewport({ scale: targetWidth / base.width })
    const canvas = document.createElement('canvas')
    canvas.width = Math.floor(viewport.width)
    canvas.height = Math.floor(viewport.height)
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas is not supported')
    await page.render({ canvasContext: ctx, canvas, viewport }).promise
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Could not render the cover'))), 'image/jpeg', 0.85),
    )
  } finally {
    void task.destroy()
  }
}
