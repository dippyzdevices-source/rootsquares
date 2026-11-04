import { optionalAuthHeaders } from './optionalAuthHeaders'

export interface Testimonial {
  id: number
  quote: string
  author_name: string
  author_context: string | null
  photo_url: string | null
  /** false only for an admin previewing a pending/rejected/hidden testimonial. */
  published?: boolean
}

export interface TestimonialListResponse {
  items: Testimonial[]
}

export interface TestimonialSubmission {
  quote: string
  author_name: string
  author_context?: string | null
  photo_url?: string | null
}

export class ValidationError extends Error {
  errors: Record<string, string>

  constructor(errors: Record<string, string>) {
    super('Validation failed')
    this.name = 'ValidationError'
    this.errors = errors
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export async function fetchTestimonials(): Promise<TestimonialListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/testimonials`, {
    headers: await optionalAuthHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch testimonials: ${response.status}`)
  }
  return response.json() as Promise<TestimonialListResponse>
}

// Public, unauthenticated — anyone may share a testimonial. It never appears on the site
// until an admin reviews and approves it (see backend/app/testimonials/models.py).
export async function submitTestimonial(payload: TestimonialSubmission): Promise<{ id: number; status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/testimonials`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    if (response.status === 400) {
      const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
      if (body.errors) {
        throw new ValidationError(body.errors)
      }
    }
    throw new Error(`Failed to submit testimonial: ${response.status}`)
  }
  return response.json() as Promise<{ id: number; status: string }>
}
