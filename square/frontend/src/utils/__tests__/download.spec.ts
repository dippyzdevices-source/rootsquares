// Tests for download (2 cases), e.g. downloadBlob; creates an object URL, clicks a temporary link, and revokes the URL.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { downloadBlob } from '../download'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('downloadBlob', () => {
  it('creates an object URL, clicks a temporary link, and revokes the URL', () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:mock')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    const blob = new Blob(['data'])
    downloadBlob(blob, 'members.xlsx')

    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(clickSpy).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })
})
