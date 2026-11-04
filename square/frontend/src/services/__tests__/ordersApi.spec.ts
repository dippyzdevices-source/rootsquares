// Tests for ordersApi (9 cases), e.g. checkout; POSTs the payload without requiring a session; attaches the bearer token when a session exists.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import { checkout, lookupOrder, fetchMyOrders, ValidationError } from '../ordersApi'

function stubFetch(response: { ok: boolean; status?: number; json?: () => unknown }) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

beforeEach(() => {
  mockGetSession.mockResolvedValue({ data: { session: null } })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('checkout', () => {
  it('POSTs the payload without requiring a session', async () => {
    const fetchMock = stubFetch({ ok: true, status: 201, json: () => ({ id: 1, order_number: 'BCA-2026-000001' }) })

    await checkout({
      event_id: 1,
      items: [{ ticket_type_id: 1, quantity: 2 }],
      customer_name: 'Priya Das',
      customer_email: 'priya@example.com',
      customer_phone: '41234567',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/orders'),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('attaches the bearer token when a session exists', async () => {
    mockGetSession.mockResolvedValue({ data: { session: { access_token: 'token-123' } } })
    const fetchMock = stubFetch({ ok: true, status: 201, json: () => ({ id: 1 }) })

    await checkout({
      event_id: 1,
      items: [{ ticket_type_id: 1, quantity: 1 }],
      customer_name: 'Priya Das',
      customer_email: 'priya@example.com',
      customer_phone: '41234567',
    })

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers).toMatchObject({ Authorization: 'Bearer token-123' })
  })

  it('throws a ValidationError on a 400', async () => {
    stubFetch({ ok: false, status: 400, json: () => Promise.resolve({ errors: { customer_email: 'This field is required.' } }) })

    await expect(
      checkout({ event_id: 1, items: [], customer_name: '', customer_email: '', customer_phone: '' }),
    ).rejects.toBeInstanceOf(ValidationError)
  })
})

describe('lookupOrder', () => {
  it('requests the order by number and email', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ order_number: 'BCA-2026-000001' }) })

    await lookupOrder('BCA-2026-000001', 'priya@example.com')

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('order_number=BCA-2026-000001')
    expect(url).toContain('email=priya%40example.com')
  })

  it('throws a not-found error on a 404', async () => {
    stubFetch({ ok: false, status: 404 })

    await expect(lookupOrder('BCA-2026-000001', 'wrong@example.com')).rejects.toThrow(
      'Order not found',
    )
  })
})

describe('fetchMyOrders', () => {
  it('sends the bearer token', async () => {
    mockGetSession.mockResolvedValue({ data: { session: { access_token: 'token-123' } } })
    const fetchMock = stubFetch({ ok: true, json: () => ({ items: [] }) })

    await fetchMyOrders()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/orders/me'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
  })
})
