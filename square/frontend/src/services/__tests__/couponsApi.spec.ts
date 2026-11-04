// Tests for couponsApi (8 cases), e.g. couponsApi; validates a coupon code, attaching the session auth header when one ex; validates a coupon code with no auth header when signed out.
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import {
  validateCoupon,
  fetchAdminCoupons,
  createAdminCoupon,
  updateAdminCoupon,
  ValidationError,
} from '../couponsApi'

beforeEach(() => {
  vi.clearAllMocks()
  mockGetSession.mockResolvedValue({ data: { session: { access_token: 'token-123' } } })
})

describe('couponsApi', () => {
  it('validates a coupon code, attaching the session auth header when one exists', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ valid: true, code: 'SAVE20', discount_percent: 20 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await validateCoupon(5, 'save20')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/coupons/validate'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    expect(fetchMock.mock.calls[0][0]).toContain('code=save20')
    expect(result.valid).toBe(true)
    expect(result.discount_percent).toBe(20)
    vi.unstubAllGlobals()
  })

  it('validates a coupon code with no auth header when signed out', async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ valid: true, code: 'SAVE20', discount_percent: 20 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await validateCoupon(5, 'save20')

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/coupons/validate'), {
      headers: {},
    })
    vi.unstubAllGlobals()
  })

  it('reports an invalid coupon without throwing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ valid: false, error: 'Invalid or inactive coupon code.' }),
      }),
    )

    const result = await validateCoupon(5, 'NOPE')

    expect(result.valid).toBe(false)
    vi.unstubAllGlobals()
  })

  it('fetches admin coupons for an event with an auth header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: 1, event_id: 5, code: 'SAVE20', discount_percent: 20, is_active: true }] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchAdminCoupons(5)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/events/5/coupons'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    expect(result.items).toHaveLength(1)
    vi.unstubAllGlobals()
  })

  it('creates a coupon', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, event_id: 5, code: 'SAVE20', discount_percent: 20, is_active: true }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createAdminCoupon(5, { code: 'SAVE20', discount_percent: 20 })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/events/5/coupons'),
      expect.objectContaining({ method: 'POST' }),
    )
    vi.unstubAllGlobals()
  })

  it('throws ValidationError on a 400 response with errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ errors: { discount_percent: 'Must be an integer from 1 to 100.' } }),
      }),
    )

    await expect(createAdminCoupon(5, { code: 'X', discount_percent: 200 })).rejects.toThrow(ValidationError)
    vi.unstubAllGlobals()
  })

  it('updates a coupon by id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, event_id: 5, code: 'SAVE20', discount_percent: 20, is_active: false }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await updateAdminCoupon(1, { is_active: false })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/coupons/1'),
      expect.objectContaining({ method: 'PATCH' }),
    )
    vi.unstubAllGlobals()
  })
})
