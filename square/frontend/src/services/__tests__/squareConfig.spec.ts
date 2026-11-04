// Tests for squareConfig (5 cases), e.g. squareConfig; never asks the server in the test suite and uses the bca-oslo fallback; takes the name, slug, theme and sign-in project of the square the serv.
import { afterEach, describe, expect, it, vi } from 'vitest'

// squareConfig.ts asks the server once, at import (top-level await), so each case stubs the environment and fetch, resets the module cache and imports it again.
async function load() {
  vi.resetModules()
  return import('../squareConfig')
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe('squareConfig', () => {
  it('never asks the server in the test suite and uses the bca-oslo fallback name', async () => {
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)
    const { squareProfile, squareAuth, FALLBACK_SQUARE_NAME } = await load()
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(squareProfile.name).toBe(FALLBACK_SQUARE_NAME)
    expect(squareAuth).toBeNull()
  })

  it('takes the name, slug, theme and sign-in project of the square the server answers with', async () => {
    vi.stubEnv('MODE', 'production')
    const answer = { slug: 'first-org', name: '  First Org  ', theme_id: 'paper-brick', currency: 'SEK', auth: { provider: 'supabase', url: 'https://x.supabase.co', public_key: 'pk' } }
    const fetchSpy = vi.fn().mockResolvedValue({ ok: true, json: async () => answer })
    vi.stubGlobal('fetch', fetchSpy)
    const { squareProfile, squareAuth } = await load()
    expect(fetchSpy).toHaveBeenCalledWith('/api/square/config')
    expect(squareProfile).toMatchObject({ name: 'First Org', slug: 'first-org', themeId: 'paper-brick', currency: 'SEK' })
    expect(squareAuth).toEqual(answer.auth)
  })

  it('falls back when the server does not know the host or cannot be reached', async () => {
    vi.stubEnv('MODE', 'production')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ error: 'Unknown square' }) }))
    expect((await load()).squareProfile.name).toBe('BCA Oslo')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const { squareProfile, squareAuth } = await load()
    expect(squareProfile.name).toBe('BCA Oslo')
    expect(squareAuth).toBeNull()
  })

  it('uses NOK when the server does not say which currency the square has', async () => {
    vi.stubEnv('MODE', 'production')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ name: 'Old', slug: 'old' }) }))
    expect((await load()).squareProfile.currency).toBe('NOK')
  })
})
