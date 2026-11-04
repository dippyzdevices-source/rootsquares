import { supabase } from './supabaseClient'

export interface TaskAssignmentRecord {
  id: number
  member_id: number
  member_name: string
  member_email: string | null
  category: string
}

export interface TaskAssignmentPayload {
  member_id?: number
  category?: string
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

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function throwForErrorResponse(response: Response): Promise<never> {
  if (response.status === 400) {
    const body = (await response.json().catch(() => ({}))) as { errors?: Record<string, string> }
    if (body.errors) {
      throw new ValidationError(body.errors)
    }
  }
  throw new Error(`Request failed: ${response.status}`)
}

export async function createTaskAssignment(
  eventId: number,
  payload: TaskAssignmentPayload,
): Promise<TaskAssignmentRecord> {
  const response = await fetch(`${API_BASE_URL}/api/admin/events/${eventId}/task-assignments`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<TaskAssignmentRecord>
}

export async function updateTaskAssignment(
  eventId: number,
  assignmentId: number,
  payload: TaskAssignmentPayload,
): Promise<TaskAssignmentRecord> {
  const response = await fetch(
    `${API_BASE_URL}/api/admin/events/${eventId}/task-assignments/${assignmentId}`,
    {
      method: 'PATCH',
      headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<TaskAssignmentRecord>
}

export async function deleteTaskAssignment(eventId: number, assignmentId: number): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/admin/events/${eventId}/task-assignments/${assignmentId}`,
    { method: 'DELETE', headers: await authHeaders() },
  )
  if (!response.ok) {
    throw new Error(`Failed to delete volunteer assignment: ${response.status}`)
  }
}
