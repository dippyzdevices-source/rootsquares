// Tests for siteContent (4 cases), e.g. siteContent; fills the keys a square did not set with empty text and no stats; loads once and shares the answer.
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockFetchSettings = vi.fn()
vi.mock('./settingsApi', () => ({ fetchSettings: () => mockFetchSettings() }))

import { EMPTY_HOME_CONTENT, fillHomeContent, loadHomeContent, resetHomeContent } from './siteContent'

beforeEach(() => {
  vi.clearAllMocks()
  resetHomeContent()
})

describe('siteContent', () => {
  it('fills the keys a square did not set with empty text and no stats', () => {
    expect(fillHomeContent(undefined)).toEqual(EMPTY_HOME_CONTENT)
    expect(fillHomeContent({ headline: 'Hello' })).toEqual({ ...EMPTY_HOME_CONTENT, headline: 'Hello' })
  })

  it('loads once and shares the answer', async () => {
    mockFetchSettings.mockResolvedValue({ home_content: { headline: 'Hello', stats: [{ value: '1', label: 'x' }] } })
    const [a, b] = await Promise.all([loadHomeContent(), loadHomeContent()])
    expect(a.headline).toBe('Hello')
    expect(b.stats).toHaveLength(1)
    expect(mockFetchSettings).toHaveBeenCalledTimes(1)
  })

  it('falls back to empty when the settings cannot be loaded and tries again next time', async () => {
    mockFetchSettings.mockRejectedValueOnce(new Error('offline'))
    expect(await loadHomeContent()).toEqual(EMPTY_HOME_CONTENT)
    mockFetchSettings.mockResolvedValue({ home_content: { headline: 'Back' } })
    expect((await loadHomeContent()).headline).toBe('Back')
  })
})
