// Tests for adminTicketTypesApi (6 cases), e.g. adminTicketTypesApi; fetches ticket types for an event with an auth header; creates a ticket type.
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGetSession = vi.fn()

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: (...args: unknown[]) => mockGetSession(...args) } },
}))

import {
  fetchAdminTicketTypes,
  createAdminTicketType,
  updateAdminTicketType,
  deleteAdminTicketType,
  ValidationError,
} from '../adminTicketTypesApi'

beforeEach(() => {
  vi.clearAllMocks()
  mockGetSession.mockResolvedValue({ data: { session: { access_token: 'token-123' } } })
})

describe('adminTicketTypesApi', () => {
  it('fetches ticket types for an event with an auth header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: 1, event_id: 5, name: 'Adult', price: 15000 }] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchAdminTicketTypes(5)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/events/5/ticket-types'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token-123' } }),
    )
    expect(result.items).toHaveLength(1)
    vi.unstubAllGlobals()
  })

  it('creates a ticket type', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, event_id: 5, name: 'Adult', price: 15000 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createAdminTicketType(5, { name: 'Adult', price: 15000 })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/events/5/ticket-types'),
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
        json: async () => ({ errors: { price: 'Must be a non-negative integer (minor units).' } }),
      }),
    )

    await expect(createAdminTicketType(5, { name: '', price: -1 })).rejects.toThrow(ValidationError)
    vi.unstubAllGlobals()
  })

  it('updates a ticket type by id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, event_id: 5, name: 'Adult VIP', price: 20000 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await updateAdminTicketType(1, { name: 'Adult VIP' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/ticket-types/1'),
      expect.objectContaining({ method: 'PATCH' }),
    )
    vi.unstubAllGlobals()
  })

  it('deletes a ticket type by id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)

    await deleteAdminTicketType(1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/ticket-types/1'),
      expect.objectContaining({ method: 'DELETE' }),
    )
    vi.unstubAllGlobals()
  })
})
