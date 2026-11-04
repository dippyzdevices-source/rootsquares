// Tests for membershipPaymentsApi (4 cases), e.g. membershipPaymentsApi; fetchMyPeriods GETs the periods endpoint; startPeriodPayment POSTs the selected period ids and provider.
import { describe, it, expect, vi, afterEach } from 'vitest'

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) } },
}))

import { fetchMyPeriods, startPeriodPayment } from '../membershipPaymentsApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('membershipPaymentsApi', () => {
  it('fetchMyPeriods GETs the periods endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ membership: null, items: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchMyPeriods()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/memberships\/me\/periods$/),
      expect.anything(),
    )
  })

  it('startPeriodPayment POSTs the selected period ids and provider', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        payment: { id: 1, payment_reference: 'PAY-2027-000001', amount: 20000, status: 'pending' },
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await startPeriodPayment({ periodIds: [1, 2], provider: 'vipps_qr' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/memberships\/me\/payments$/),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ membership_period_ids: [1, 2], provider: 'vipps_qr' }),
      }),
    )
    expect(result.payment.status).toBe('pending')
  })

  it('throws when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))

    await expect(fetchMyPeriods()).rejects.toThrow('500')
  })
})
