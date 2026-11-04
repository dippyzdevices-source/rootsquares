// Tests for PdfReader (7 cases), e.g. PdfReader; loads the document, renders page 1 and shows the page count; turns pages with the next/previous buttons and clamps at the ends.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockRender = vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() }))
const mockGetPage = vi.fn(async () => ({
  getViewport: ({ scale }: { scale: number }) => ({ width: 600 * scale, height: 800 * scale }),
  render: mockRender,
}))
const mockGetDocument = vi.fn()

vi.mock('../../../utils/pdfjs', () => ({
  loadPdfJs: async () => ({ getDocument: (...args: unknown[]) => mockGetDocument(...args) }),
}))

import PdfReader from '../PdfReader.vue'

beforeEach(() => {
  vi.clearAllMocks()
  // jsdom has no canvas implementation.
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ setTransform: vi.fn() })) as never
})

function openDoc(numPages: number) {
  mockGetDocument.mockReturnValue({
    promise: Promise.resolve({ numPages, getPage: mockGetPage, destroy: vi.fn() }),
  })
}

describe('PdfReader', () => {
  it('loads the document, renders page 1 and shows the page count', async () => {
    openDoc(5)
    const wrapper = mount(PdfReader, { props: { url: 'https://cdn/x.pdf', title: 'Puja' } })
    await flushPromises()

    expect(mockGetDocument).toHaveBeenCalledWith(expect.objectContaining({ url: 'https://cdn/x.pdf' }))
    expect(mockGetPage).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('/ 5')
  })

  it('turns pages with the next/previous buttons and clamps at the ends', async () => {
    openDoc(2)
    const wrapper = mount(PdfReader, { props: { url: 'https://cdn/x.pdf' } })
    await flushPromises()

    const prev = wrapper.find('button[aria-label="Previous page"]')
    const next = wrapper.find('button[aria-label="Next page"]')
    expect(prev.attributes('disabled')).toBeDefined()

    await next.trigger('click')
    await flushPromises()
    expect(mockGetPage).toHaveBeenLastCalledWith(2)
    expect(next.attributes('disabled')).toBeDefined()
    expect((wrapper.find('input[aria-label="Page number"]').element as HTMLInputElement).value).toBe('2')
  })

  it('offers a download/open fallback when the PDF cannot be loaded', async () => {
    mockGetDocument.mockReturnValue({ promise: Promise.reject(new Error('cors')) })
    const wrapper = mount(PdfReader, { props: { url: 'https://cdn/x.pdf' } })
    await flushPromises()

    expect(wrapper.text()).toContain('Could not open this magazine here')
    expect(wrapper.find('a.pdf-fallback').attributes('href')).toBe('https://cdn/x.pdf')
  })

  it('opens the PDF as a plain whole-file request (no Range/stream, so no CORS preflight)', async () => {
    openDoc(3)
    mount(PdfReader, { props: { url: 'https://cdn/x.pdf', title: 'Puja' } })
    await flushPromises()
    expect(mockGetDocument).toHaveBeenCalledWith(expect.objectContaining({ url: 'https://cdn/x.pdf', disableRange: true, disableStream: true }))
  })

  it('logs the real error and shows it under the fallback link when the PDF cannot be opened', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockGetDocument.mockReturnValue({ promise: Promise.reject(new Error('Failed to fetch')) })
    const wrapper = mount(PdfReader, { props: { url: 'https://cdn/x.pdf', title: 'Puja' } })
    await flushPromises()

    expect(wrapper.text()).toContain('Could not open this magazine here')
    expect(wrapper.find('.pdf-error-detail').text()).toBe('Failed to fetch')
    expect(wrapper.find('a.pdf-fallback').attributes('href')).toBe('https://cdn/x.pdf')
    expect(log).toHaveBeenCalled()
    log.mockRestore()
  })

  it('shows a Close button only when closable, and emits close', async () => {
    openDoc(2)
    const plain = mount(PdfReader, { props: { url: 'https://cdn/x.pdf' } })
    await flushPromises()
    expect(plain.find('.pdf-close').exists()).toBe(false)

    openDoc(2)
    const wrapper = mount(PdfReader, { props: { url: 'https://cdn/x.pdf', closable: true } })
    await flushPromises()
    await wrapper.find('.pdf-close').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
