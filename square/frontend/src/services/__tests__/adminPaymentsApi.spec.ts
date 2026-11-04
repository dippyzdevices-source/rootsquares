// Tests for adminPaymentsApi (5 cases), e.g. exportPayments; sends the bearer token and resolves with a blob; adminPaymentsApi — reconciliation.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import { exportPayments, fetchAdminPayments, refundPayment } from '../adminPaymentsApi'

beforeEach(() => {
  vi.clearAllMocks()
  mockGetSession.mockResolvedValue({ data: { session: { access_token: 'token-123' } } })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('exportPayments', () => {
  it('sends the bearer token and resolves with a blob', async () => {
    const blob = new Blob(['xlsx-data'])
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => blob })
    vi.stubGlobal('fetch', fetchMock)

    const result = await exportPayments()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/payments/export'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    expect(result).toBe(blob)
  })
})

describe('adminPaymentsApi — reconciliation', () => {
  it('fetchAdminPayments GETs the admin payments endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminPayments()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/admin\/payments$/),
      expect.anything(),
    )
  })

  it('refundPayment POSTs to the refund endpoint with the reason', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, status: 'refunded' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await refundPayment(1, 'Member paid by mistake')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/admin\/payments\/1\/refund$/),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ reason: 'Member paid by mistake' }),
      }),
    )
  })
})
