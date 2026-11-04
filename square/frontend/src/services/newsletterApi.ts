const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

async function post(path: string, body: unknown): Promise<Response> {
  return fetch(`${API_BASE_URL}/api/newsletter/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/** Asks to subscribe an address: the server e-mails a confirm link and the address joins the list only when it is clicked. Resolves on success; throws an Error carrying the field message on 400. */
export async function subscribeNewsletter(email: string): Promise<void> {
  const response = await post('subscribe', { email, consent: true })
  if (response.status === 400) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    throw new Error(body.errors?.email ?? 'Enter a valid email address.')
  }
  if (!response.ok) {
    throw new Error('Could not subscribe right now — please try again.')
  }
}

/** Confirms a subscription from the link in the e-mail (double opt-in). Returns false when the link's token is not recognised. */
export async function confirmNewsletter(token: string): Promise<boolean> {
  const response = await post('confirm', { token })
  if (response.status === 404) return false
  if (!response.ok) throw new Error(`Confirm failed: ${response.status}`)
  return true
}

/** Returns false when the link's token is not recognised. */
export async function unsubscribeNewsletter(token: string): Promise<boolean> {
  const response = await post('unsubscribe', { token })
  if (response.status === 404) return false
  if (!response.ok) throw new Error(`Unsubscribe failed: ${response.status}`)
  return true
}
