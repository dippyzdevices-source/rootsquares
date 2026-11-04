// Tests for testimonialsApi (7 cases), e.g. fetchTestimonials; requests the testimonials list and resolves with the parsed response; throws when the response is not ok.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { fetchTestimonials, submitTestimonial, ValidationError } from '../testimonialsApi'

function stubFetch(response: { ok: boolean; status?: number; json?: () => unknown }) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchTestimonials', () => {
  it('requests the testimonials list and resolves with the parsed response', async () => {
    const body = { items: [{ id: 1, quote: 'Great!', author_name: 'Priya', author_context: null, photo_url: null }] }
    stubFetch({ ok: true, json: () => body })

    const result = await fetchTestimonials()

    expect(result).toEqual(body)
  })

  it('throws when the response is not ok', async () => {
    stubFetch({ ok: false, status: 500 })

    await expect(fetchTestimonials()).rejects.toThrow('Failed to fetch testimonials: 500')
  })
})

describe('submitTestimonial', () => {
  it('posts the submission and resolves with the pending status', async () => {
    const fetchMock = stubFetch({ ok: true, json: () => ({ id: 1, status: 'pending' }) })

    const result = await submitTestimonial({ quote: 'Great!', author_name: 'Priya Das' })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/testimonials'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ quote: 'Great!', author_name: 'Priya Das' }),
      }),
    )
    expect(result).toEqual({ id: 1, status: 'pending' })
  })

  it('throws a ValidationError for a 400 response with field errors', async () => {
    stubFetch({ ok: false, status: 400, json: async () => ({ errors: { author_name: 'This field is required.' } }) })

    await expect(submitTestimonial({ quote: 'Great!', author_name: '' })).rejects.toBeInstanceOf(ValidationError)
  })

  it('throws a generic error for a non-400 failure', async () => {
    stubFetch({ ok: false, status: 500 })

    await expect(submitTestimonial({ quote: 'Great!', author_name: 'Priya Das' })).rejects.toThrow(
      'Failed to submit testimonial: 500',
    )
  })
})
