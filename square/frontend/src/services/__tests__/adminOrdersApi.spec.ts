// Tests for adminOrdersApi (6 cases), e.g. adminOrdersApi; fetches a page of orders with an auth header; passes payment_status and event_id filters as query params.
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import { fetchAdminOrders, fetchAdminOrder, markOrderPaid, exportOrders } from '../adminOrdersApi'

beforeEach(() => {
  vi.clearAllMocks()
  mockGetSession.mockResolvedValue({ data: { session: { access_token: 'token-123' } } })
})

describe('adminOrdersApi', () => {
  it('fetches a page of orders with an auth header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminOrders()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/orders'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    vi.unstubAllGlobals()
  })

  it('passes payment_status and event_id filters as query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminOrders({ paymentStatus: 'pending', eventId: 5 })

    const calledUrl = fetchMock.mock.calls[0][0] as string
    expect(calledUrl).toContain('payment_status=pending')
    expect(calledUrl).toContain('event_id=5')
    vi.unstubAllGlobals()
  })

  it('fetches a single order by id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, order_number: 'BCA-2026-000001' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const order = await fetchAdminOrder(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/orders/1'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    expect(order.order_number).toBe('BCA-2026-000001')
    vi.unstubAllGlobals()
  })

  it('marks an order as paid', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, payment_status: 'paid' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const order = await markOrderPaid(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/orders/1/mark-paid'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(order.payment_status).toBe('paid')
    vi.unstubAllGlobals()
  })

  it('exports orders as a blob', async () => {
    const blob = new Blob(['xlsx-data'])
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => blob })
    vi.stubGlobal('fetch', fetchMock)

    const result = await exportOrders()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/orders/export'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    expect(result).toBe(blob)
    vi.unstubAllGlobals()
  })
})
