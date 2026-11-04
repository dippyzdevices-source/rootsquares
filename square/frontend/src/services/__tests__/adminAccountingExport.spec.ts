// Tests for adminAccountingExport (8 cases), e.g. exportEventExpenses; GETs the event\; throws when the server refuses.
import { describe, it, expect, vi, afterEach } from 'vitest'

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) } },
}))

import { exportEventBuyers, exportEventExpenses } from '../adminAccountingApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('exportEventExpenses', () => {
  it('GETs the event\'s expenses export and returns the file blob', async () => {
    const blob = new Blob(['x'])
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => blob })
    vi.stubGlobal('fetch', fetchMock)

    await expect(exportEventExpenses(7)).resolves.toBe(blob)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/admin\/accounting\/events\/7\/expenses\/export$/),
      expect.anything(),
    )
  })

  it('throws when the server refuses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    await expect(exportEventExpenses(7)).rejects.toThrow('Failed to export expenses: 500')
  })
})

describe('exportEventBuyers', () => {
  it('GETs the event\'s buyers export and returns the file blob', async () => {
    const blob = new Blob(['x'])
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => blob })
    vi.stubGlobal('fetch', fetchMock)

    await expect(exportEventBuyers(7)).resolves.toBe(blob)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/admin\/accounting\/events\/7\/collections\/export$/),
      expect.anything(),
    )
  })

  it('throws when the server refuses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403 }))
    await expect(exportEventBuyers(7)).rejects.toThrow('Failed to export buyers: 403')
  })
})

describe('multi-value filters', () => {
  it('sends each list filter comma-separated and omits empty ones', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['x']) })
    vi.stubGlobal('fetch', fetchMock)

    await exportEventBuyers(7, { paymentMethods: ['cash', 'vipps_qr'], couponCodes: [], ticketTypeIds: [3, 4] })
    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('payment_method=cash%2Cvipps_qr')
    expect(url).toContain('ticket_type_id=3%2C4')
    expect(url).not.toContain('coupon_code')

    await exportEventExpenses(7, { categories: ['venue', 'food'] })
    expect(String(fetchMock.mock.calls[1][0])).toMatch(/expenses\/export\?category=venue%2Cfood$/)
  })
})
