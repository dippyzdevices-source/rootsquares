// Tests for adminReportsApi (3 cases), e.g. adminReportsApi; fetchReportsSummary GETs the admin reports summary endpoint; throws when the request fails.
import { describe, it, expect, vi, afterEach } from 'vitest'

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) } },
}))

import { fetchReportsSummary } from '../adminReportsApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('adminReportsApi', () => {
  it('fetchReportsSummary GETs the admin reports summary endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        revenue_total: 15000,
        tickets_total: 2,
        tickets_checked_in: 1,
        memberships_by_status: { active: 2 },
        memberships_by_type: { individual: 2 },
        orders_by_status: { paid: 1 },
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchReportsSummary()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/reports/summary'),
      expect.anything(),
    )
    expect(result.revenue_total).toBe(15000)
  })

  it('throws when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))

    await expect(fetchReportsSummary()).rejects.toThrow('500')
  })
})
