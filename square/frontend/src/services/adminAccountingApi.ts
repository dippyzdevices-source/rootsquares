import { supabase } from './supabaseClient'

export interface AccountingEventSummary {
  event: {
    id: number
    title: string
    slug: string
    published: boolean
    start_datetime: string
    end_datetime: string | null
  }
  collection_total: number
  /** Paid donations and sponsorships (øre); both are already part of collection_total. */
  donations_total: number
  /** Donations / sponsorships still waiting to be received or confirmed (not in the Collection). */
  pending_contributions: number
  sponsorships_total: number
  expenses_total: number
  /** Expenses split: entered by hand vs the providers' estimated processing fees (øre). */
  recorded_expenses_total: number
  processing_fees_total: number
  /** Per provider: convenience fee customers paid (in Collection) and processing fee taken (in Expenses). */
  fees_by_provider: { provider: string; convenience: number; processing: number; /** Part of `processing` that came from online donations. */ processing_donations?: number }[]
  net_total: number
  tickets_sold: number
  /** Tickets that can still be scanned (not voided) and how many were checked in at the door. */
  tickets_expected: number
  tickets_checked_in: number
  tickets_by_type: { name: string; count: number; valid_on: string | null }[]
  tickets_by_sale_mode: { provider: string; count: number; /** Charged on paid payments (øre), convenience fee included. */ amount: number }[]
  top_expense_categories: { category: string; amount: number }[]
  coupon_usage: {
    coupon_code: string
    orders_count: number
    tickets_count: number
    discount_total: number
    /** What buyers paid after the discount, and the same tickets' price before it (øre). */
    paid_total: number
    gross_total: number
    by_ticket_type: { name: string; count: number; valid_on: string | null }[]
    /** The coupon's own setup; null when the coupon has since been removed. */
    discount_percent: number | null
    is_active: boolean | null
    max_redemptions: number | null
  }[]
}

export interface CollectionItem {
  id: number
  date: string
  order_number: string
  customer_name: string
  customer_email: string
  /** What was bought, one line per ticket type, e.g. ["2 × Adult", "1 × Child"]. */
  tickets: string[]
  /** null for an order with no payment record (e.g. a free order). */
  payment_method: string | null
  /** The coupon applied to the order, if any (a 100%-off order has no payment record). */
  coupon_code?: string | null
  amount: number
  payment_status: string
}

export interface Expense {
  id: number
  event_id: number | null
  date: string
  description: string
  category: string
  amount: number
  vendor: string | null
  notes: string | null
  receipt_key: string | null
  receipt_url: string | null
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface ExpensesPage {
  items: Expense[]
  page: number
  per_page: number
  total: number
  total_pages: number
  /** Read-only "<Provider> processing fees" lines shown above the recorded expenses. */
  processing_fee_lines?: { provider: string; amount: number }[]
}

export interface ExpenseFilter {
  page?: number
  perPage?: number
  categories?: string[]
  dateFrom?: string
  dateTo?: string
  q?: string
}

export interface ExpensePayload {
  date?: string
  description?: string
  category?: string
  amount?: number
  vendor?: string | null
  notes?: string | null
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
const BASE_URL = `${API_BASE_URL}/api/admin/accounting`

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

/** An event's book, or the general book (no event) when the id is null (W14-R15). */
const bookPath = (eventId: number | null) => (eventId === null ? '/general' : `/events/${eventId}`)

export interface GeneralSummary {
  currency: string
  income: { total: number; by_source: { source: string; label: string; count: number; total: number }[] }
  expenses: { total: number; count: number; by_category: { category: string; label: string; total: number }[] }
  net: number
}
/** `id` and `notes` are set for income typed in by hand (source 'manual'), which can be changed and deleted. */
export interface GeneralIncomeRow { source: string; id?: number; reference: string | null; name: string | null; date: string; amount: number; notes?: string | null }
export interface ManualIncome { id: number; date: string; description: string; amount: number; source_name: string | null; notes: string | null }
export interface ManualIncomePayload { date: string; description: string; amount: number; source_name: string | null; notes: string | null }

export async function fetchGeneralSummary(range: { dateFrom?: string; dateTo?: string } = {}): Promise<GeneralSummary> {
  const response = await fetch(`${BASE_URL}/general${rangeQuery(range)}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<GeneralSummary>
}

export async function fetchGeneralIncome(range: { dateFrom?: string; dateTo?: string } = {}): Promise<GeneralIncomeRow[]> {
  const response = await fetch(`${BASE_URL}/general/income${rangeQuery(range)}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return ((await response.json()) as { items: GeneralIncomeRow[] }).items
}

export async function createManualIncome(payload: ManualIncomePayload): Promise<ManualIncome> {
  const response = await fetch(`${BASE_URL}/general/manual-income`, { method: 'POST', headers: { ...(await authHeaders()), 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<ManualIncome>
}

export async function updateManualIncome(id: number, payload: ManualIncomePayload): Promise<ManualIncome> {
  const response = await fetch(`${BASE_URL}/general/manual-income/${id}`, { method: 'PATCH', headers: { ...(await authHeaders()), 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<ManualIncome>
}

export async function deleteManualIncome(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/general/manual-income/${id}`, { method: 'DELETE', headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
}

export interface BudgetRow { category: string; label: string; budget: number; spent: number; remaining: number }
export interface IncomeTargetRow { source: string; label: string; target: number; received: number; remaining: number }
export interface GeneralBudget {
  year: number
  currency: string
  items: BudgetRow[]
  budget_total: number
  spent_total: number
  income: IncomeTargetRow[]
  income_target_total: number
  income_received_total: number
  /** The income target minus the expense budget: what the square plans to keep. */
  planned_net: number
}

export async function fetchGeneralBudget(year: number): Promise<GeneralBudget> {
  const response = await fetch(`${BASE_URL}/general/budget?year=${year}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<GeneralBudget>
}

/** Sets the budget of one category for a year, in minor units; 0 removes it. */
export async function setGeneralBudget(year: number, category: string, amount: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/general/budget`, { method: 'PUT', headers: { ...(await authHeaders()), 'Content-Type': 'application/json' }, body: JSON.stringify({ year, category, amount }) })
  if (!response.ok) return throwForErrorResponse(response)
}

/** Sets the income target of one source (donation, membership, manual) for a year, in minor units; 0 removes it. */
export async function setGeneralIncomeTarget(year: number, source: string, amount: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/general/budget/income`, { method: 'PUT', headers: { ...(await authHeaders()), 'Content-Type': 'application/json' }, body: JSON.stringify({ year, source, amount }) })
  if (!response.ok) return throwForErrorResponse(response)
}

/** Copies the budgets and income targets of the year before into a year, filling only what is not set there yet. */
export async function copyGeneralBudget(year: number): Promise<{ year: number; from_year: number; budgets: number; targets: number }> {
  const response = await fetch(`${BASE_URL}/general/budget/copy`, { method: 'POST', headers: { ...(await authHeaders()), 'Content-Type': 'application/json' }, body: JSON.stringify({ year }) })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<{ year: number; from_year: number; budgets: number; targets: number }>
}

/** The general book as a PDF report, narrowed to the same range as the page; a whole year adds the budget. */
export async function exportGeneralReport(range: { dateFrom?: string; dateTo?: string } = {}): Promise<Blob> {
  const response = await fetch(`${BASE_URL}/general/report${rangeQuery(range)}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to build the report: ${response.status}`)
  return response.blob()
}

export async function exportGeneralBook(range: { dateFrom?: string; dateTo?: string } = {}): Promise<Blob> {
  const response = await fetch(`${BASE_URL}/general/export${rangeQuery(range)}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Failed to export: ${response.status}`)
  return response.blob()
}

function rangeQuery(range: { dateFrom?: string; dateTo?: string }): string {
  const params = new URLSearchParams()
  if (range.dateFrom) params.set('date_from', range.dateFrom)
  if (range.dateTo) params.set('date_to', range.dateTo)
  const query = params.toString()
  return query ? `?${query}` : ''
}

export async function fetchEventAccountingSummary(eventId: number): Promise<AccountingEventSummary> {
  const response = await fetch(`${BASE_URL}/events/${eventId}`, { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<AccountingEventSummary>
}

/** Narrows an event's Collections: free-text search, how it was paid ('coupon' = a free coupon order), coupons, ticket types.
 * Each list filter takes several values (sent comma-separated); an empty or missing list means no filter. */
export interface CollectionsFilter {
  q?: string
  paymentMethods?: string[]
  /** Only orders that used one of these coupon codes. */
  couponCodes?: string[]
  ticketTypeIds?: number[]
}

function collectionsQuery(filter: CollectionsFilter): string {
  const params = new URLSearchParams()
  if (filter.q) params.set('q', filter.q)
  if (filter.paymentMethods?.length) params.set('payment_method', filter.paymentMethods.join(','))
  if (filter.couponCodes?.length) params.set('coupon_code', filter.couponCodes.join(','))
  if (filter.ticketTypeIds?.length) params.set('ticket_type_id', filter.ticketTypeIds.join(','))
  const query = params.toString()
  return query ? `?${query}` : ''
}

export async function fetchEventCollections(
  eventId: number,
  filter: CollectionsFilter = {},
): Promise<{ items: CollectionItem[] }> {
  const response = await fetch(`${BASE_URL}/events/${eventId}/collections${collectionsQuery(filter)}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<{ items: CollectionItem[] }>
}

/** Paid buyers of one event as an .xlsx: a "Buyers" sheet (one row per order) and a "Tickets" sheet (one row per ticket). */
export async function exportEventBuyers(eventId: number, filter: CollectionsFilter = {}): Promise<Blob> {
  const response = await fetch(`${BASE_URL}/events/${eventId}/collections/export${collectionsQuery(filter)}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Failed to export buyers: ${response.status}`)
  return response.blob()
}

/** The whole accounting page for one event as a single PDF report; `details` adds what each order bought. */
export async function downloadEventReport(eventId: number, options: { details?: boolean } = {}): Promise<Blob> {
  const response = await fetch(`${BASE_URL}/events/${eventId}/report${options.details ? '?details=1' : ''}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Failed to build the report: ${response.status}`)
  return response.blob()
}

/** An event's expenses as an .xlsx (oldest first, with a Total row); all of them unless categories are given. */
export async function exportEventExpenses(eventId: number, filter: { categories?: string[] } = {}): Promise<Blob> {
  const query = filter.categories?.length ? `?category=${encodeURIComponent(filter.categories.join(','))}` : ''
  const response = await fetch(`${BASE_URL}/events/${eventId}/expenses/export${query}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Failed to export expenses: ${response.status}`)
  return response.blob()
}

export async function fetchEventExpenses(
  eventId: number | null,
  filter: ExpenseFilter = {},
): Promise<ExpensesPage> {
  const params = new URLSearchParams()
  if (filter.page) params.set('page', String(filter.page))
  if (filter.perPage) params.set('per_page', String(filter.perPage))
  if (filter.categories?.length) params.set('category', filter.categories.join(','))
  if (filter.dateFrom) params.set('date_from', filter.dateFrom)
  if (filter.dateTo) params.set('date_to', filter.dateTo)
  if (filter.q) params.set('q', filter.q)

  const query = params.toString()
  const response = await fetch(
    `${BASE_URL}${bookPath(eventId)}/expenses${query ? `?${query}` : ''}`,
    { headers: await authHeaders() },
  )
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<ExpensesPage>
}

export async function createExpense(eventId: number | null, payload: ExpensePayload): Promise<Expense> {
  const response = await fetch(`${BASE_URL}${bookPath(eventId)}/expenses`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<Expense>
}

export async function updateExpense(expenseId: number, payload: ExpensePayload): Promise<Expense> {
  const response = await fetch(`${BASE_URL}/expenses/${expenseId}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<Expense>
}

export async function deleteExpense(expenseId: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/expenses/${expenseId}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
}

export async function uploadExpenseReceipt(expenseId: number, file: File): Promise<Expense> {
  const formData = new FormData()
  formData.append('file', file)
  // No 'Content-Type' header here — the browser sets the multipart boundary itself.
  const response = await fetch(`${BASE_URL}/expenses/${expenseId}/receipt`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<Expense>
}

export async function deleteExpenseReceipt(expenseId: number): Promise<Expense> {
  const response = await fetch(`${BASE_URL}/expenses/${expenseId}/receipt`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<Expense>
}

export type ContributionKind = 'donation' | 'sponsorship'

export interface Contribution {
  id: number
  event_id: number
  kind: ContributionKind
  name: string
  email: string | null
  /** Null for a sponsorship enquiry that named no amount yet. */
  amount: number | null
  contact_name: string | null
  phone: string | null
  website: string | null
  requirements: string | null
  date: string
  payment_method: string | null
  notes: string | null
  status: string
  created_by: string | null
  created_at: string
}

export interface ContributionPayload {
  kind?: ContributionKind
  name?: string
  email?: string | null
  amount?: number
  date?: string
  payment_method?: string | null
  notes?: string | null
  contact_name?: string | null
  phone?: string | null
  website?: string | null
  requirements?: string | null
  status?: 'pending' | 'paid'
}

export async function fetchEventContributions(
  eventId: number,
  filter: { kinds?: string[]; q?: string } = {},
): Promise<{ items: Contribution[]; total: number }> {
  const params = new URLSearchParams()
  if (filter.kinds?.length) params.set('kind', filter.kinds.join(','))
  if (filter.q) params.set('q', filter.q)
  const query = params.toString()
  const response = await fetch(`${BASE_URL}/events/${eventId}/contributions${query ? `?${query}` : ''}`, {
    headers: await authHeaders(),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<{ items: Contribution[]; total: number }>
}

export async function createContribution(eventId: number, payload: ContributionPayload): Promise<Contribution> {
  const response = await fetch(`${BASE_URL}/events/${eventId}/contributions`, {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<Contribution>
}

export async function updateContribution(id: number, payload: ContributionPayload): Promise<Contribution> {
  const response = await fetch(`${BASE_URL}/contributions/${id}`, {
    method: 'PATCH',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return throwForErrorResponse(response)
  return response.json() as Promise<Contribution>
}

export async function deleteContribution(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/contributions/${id}`, { method: 'DELETE', headers: await authHeaders() })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
}
