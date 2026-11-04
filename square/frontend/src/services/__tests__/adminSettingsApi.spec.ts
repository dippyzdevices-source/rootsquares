// Tests for adminSettingsApi (4 cases), e.g. adminSettingsApi; fetchAdminSettings GETs the admin settings endpoint; updateAdminSettings PATCHes the given fields.
import { describe, it, expect, vi, afterEach } from 'vitest'

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) } },
}))

import { fetchAdminSettings, updateAdminSettings, ValidationError } from '../adminSettingsApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('adminSettingsApi', () => {
  it('fetchAdminSettings GETs the admin settings endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ contact_email: 'a@b.com', contact_phone: '', contact_address: '' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminSettings()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/settings'),
      expect.anything(),
    )
  })

  it('updateAdminSettings PATCHes the given fields', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ contact_email: 'new@bcaoslo.no', contact_phone: '', contact_address: '' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await updateAdminSettings({ contact_email: 'new@bcaoslo.no' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/settings'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ contact_email: 'new@bcaoslo.no' }),
      }),
    )
    expect(result.contact_email).toBe('new@bcaoslo.no')
  })

  it('throws ValidationError on a 400 with field errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ errors: { contact_email: 'Must be a string.' } }),
      }),
    )

    await expect(updateAdminSettings({ contact_email: 'x' })).rejects.toBeInstanceOf(
      ValidationError,
    )
  })
})
