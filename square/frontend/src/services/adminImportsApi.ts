import { supabase } from './supabaseClient'

export interface ImportRowPreview {
  row_number: number
  name?: string
  email?: string | null
  parent_email?: string | null
  phone?: string | null
  address?: string | null
  family_info?: string | null
  membership_type?: string
  membership_status?: string
  start_date?: string
  end_date?: string | null
  errors: Record<string, string>
}

export interface ImportFailure {
  row_number: number | null
  name: string | null
  reason: string
}

export interface ImportPreviewResponse {
  rows: ImportRowPreview[]
  valid_count: number
  invalid_count: number
}

export interface ImportBatch {
  id: number
  filename: string
  admin_email: string | null
  total_rows: number
  members_created: number
  memberships_created: number
  failed_rows: number
  created_at: string
  // Only on a fresh confirm response (not stored in history): why each skipped row was skipped.
  failures?: ImportFailure[]
}

export interface ImportHistoryPage {
  items: ImportBatch[]
  page: number
  per_page: number
  total: number
  total_pages: number
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string
const BASE_URL = `${API_BASE_URL}/api/admin/imports`

async function authHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function previewMembersImport(file: File): Promise<ImportPreviewResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${BASE_URL}/members/preview`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) {
    throw new Error(`Failed to preview import: ${response.status}`)
  }
  return response.json() as Promise<ImportPreviewResponse>
}

export async function confirmMembersImport(
  filename: string,
  rows: Record<string, unknown>[],
): Promise<ImportBatch> {
  const response = await fetch(`${BASE_URL}/members/confirm`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, rows }),
  })
  if (!response.ok) {
    throw new Error(`Failed to confirm import: ${response.status}`)
  }
  return response.json() as Promise<ImportBatch>
}

export async function fetchImportHistory(page = 1): Promise<ImportHistoryPage> {
  const search = new URLSearchParams({ page: String(page) })
  const response = await fetch(`${BASE_URL}?${search.toString()}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch import history: ${response.status}`)
  }
  return response.json() as Promise<ImportHistoryPage>
}
