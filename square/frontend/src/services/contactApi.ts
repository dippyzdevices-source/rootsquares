export interface ContactSubmission {
  name: string
  email: string
  subject: string
  message: string
  website?: string
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

// Public, unauthenticated — the Contact Us form. The backend sends the email (via Resend);
// nothing here ever talks to an email provider directly.
export async function submitContactForm(payload: ContactSubmission): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/contact`, {
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
    if (response.status === 429 || response.status === 503) {
      const body = (await response.json().catch(() => ({}))) as { error?: string }
      throw new Error(body.error || 'We could not send your message right now. Please try again later.')
    }
    throw new Error(`Failed to submit contact form: ${response.status}`)
  }

  return response.json() as Promise<{ success: boolean; message: string }>
}
