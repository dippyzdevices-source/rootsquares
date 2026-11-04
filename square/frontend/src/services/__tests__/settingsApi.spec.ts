// Tests for settingsApi (3 cases), e.g. settingsApi; fetchSettings GETs the public settings endpoint; throws when the request fails.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { fetchSettings } from '../settingsApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('settingsApi', () => {
  it('fetchSettings GETs the public settings endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ contact_email: 'a@b.com', contact_phone: '123', contact_address: 'Oslo' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchSettings()

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/settings'))
    expect(result.contact_email).toBe('a@b.com')
  })

  it('throws when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))

    await expect(fetchSettings()).rejects.toThrow('500')
  })
})
