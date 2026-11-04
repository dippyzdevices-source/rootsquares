// Tests for adminTestimonialsApi (5 cases), e.g. adminTestimonialsApi; fetchAdminTestimonials GETs the list with no filter by default; fetchAdminTestimonials appends a status filter when given.
import { describe, it, expect, vi, afterEach } from 'vitest'

vi.mock('../supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) } },
}))

import { fetchAdminTestimonials, updateAdminTestimonial } from '../adminTestimonialsApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('adminTestimonialsApi', () => {
  it('fetchAdminTestimonials GETs the list with no filter by default', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminTestimonials()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/admin\/testimonials$/),
      expect.anything(),
    )
  })

  it('fetchAdminTestimonials appends a status filter when given', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminTestimonials('pending')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('status=pending'),
      expect.anything(),
    )
  })

  it('fetchAdminTestimonials appends an optional per_page override alongside status', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], page: 1, per_page: 1, total: 0, total_pages: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminTestimonials('pending', 1)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('status=pending'),
      expect.anything(),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('per_page=1'),
      expect.anything(),
    )
  })

  it('updateAdminTestimonial can approve a pending submission', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, status: 'approved', is_active: true }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await updateAdminTestimonial(1, { status: 'approved', is_active: true })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/testimonials/1'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ status: 'approved', is_active: true }),
      }),
    )
  })
})
