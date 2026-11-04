// The admin application's client of the staff API (ADR 083): /api/admin/v1, the cookie `rs_admin` (set by the server, HttpOnly), the header the server asks for, problem+json errors.
// It knows nothing of the customer API, the identity provider or the customer's cookies. The pages in admin/features call it as `platform` (import { adminApi as platform }).
import { ApiError, type MailDomain, type SiteDomain, type BillingOrder, type InvoiceSeller, type ModuleCatalogue, type PlanPrice, type PlatformSquare, type PlatformVoucher, type Prospect, type VoucherInput } from '@rootsquares/ui/types/platformTypes'
import { type OpexActual, type OpexAssumptions, type OpexForecast, type OpexInput, type OpexItem, type OpexList, type OpexMonthly, type OpexRate, type OpexScenarioName, type OwnerAttentionList, type OwnerAuditItem, type OwnerAuditQuery, type OwnerHealth, type OwnerOrg, type OwnerOverview, type OwnerSquare, type OwnerSquareDetail, type OwnerSubscriptions, type OwnerUser, type OwnerUserDetail, type PartnerInput, type PartnerReport, type PlatformPartner, type VoucherRedemption, type VoucherSettings, type SupportOverview, type SupportSessionStart, type SupportSquareState } from './adminTypes'

const BASE = ((import.meta.env.VITE_ADMIN_API_BASE_URL as string | undefined) ?? 'http://localhost:5001').replace(/\/$/, '') + '/api/admin/v1'

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(BASE + path, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'rootsquares-admin', ...(init.headers ?? {}) },
  })
}

async function toError(r: Response): Promise<ApiError> {
  let body: { code?: string; detail?: string; title?: string; errors?: { loc: (string | number)[]; msg: string }[] } = {}
  try { body = await r.json() } catch { /* not JSON */ }
  return new ApiError(r.status, body.code ?? 'http_error', body.detail ?? body.title ?? `HTTP ${r.status}`, body.errors ?? [], body as Record<string, unknown>)
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  let r: Response
  try { r = await raw(path, init) } catch { throw new ApiError(0, 'network_error', 'The server is not reachable') }
  if (r.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('admin-signed-out')) // idle too long, signed out elsewhere, switched off
  if (!r.ok) throw await toError(r)
  return (await r.json()) as T
}

const post = (body?: unknown): RequestInit => ({ method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

/** Where a staff sign-in stands: 'enrol' = the authenticator app is not set up yet, 'totp' = a code is asked for, 'signed_in' = done. */
export type StaffStep = 'enrol' | 'totp' | 'signed_in'
export interface StaffMember { id: string; email: string; name: string }
export interface StaffSessionInfo { step: StaffStep; staff: StaffMember }

export interface StaffSessionRow { id: string; created_at: string; last_seen_at: string | null; current: boolean; ip_tag: string | null }

export const staffApi = {
  me: () => call<StaffSessionInfo>('/auth/me'),
  login: (email: string, password: string) => call<StaffSessionInfo>('/auth/login', post({ email, password })),
  enrolStart: () => call<{ secret: string; otpauth_uri: string }>('/auth/enrol/start', post()),
  enrolConfirm: (code: string) => call<StaffSessionInfo & { recovery_codes: string[] }>('/auth/enrol/confirm', post({ code })),
  totp: (code: string) => call<StaffSessionInfo>('/auth/totp', post({ code })),
  logout: async () => { await call('/auth/logout', post()) },
  sessions: async () => (await call<{ items: StaffSessionRow[] }>('/auth/sessions')).items,
  revokeOthers: async () => (await call<{ revoked: number }>('/auth/sessions/revoke-others', post())).revoked,
  logoutAll: async () => (await call<{ revoked: number }>('/auth/logout-all', post())).revoked,
}

export interface AdminApi {
  /** Platform admin: can the platform reach the square's own database? */
  checkSquare(id: string): Promise<{ ok: boolean; admins: number | null }>
  createOpex(input: OpexInput): Promise<OpexItem>
  createPartner(input: PartnerInput): Promise<PlatformPartner>
  createVoucher(input: VoucherInput): Promise<PlatformVoucher>
  /** Platform admin: the guiding minimum per month (USD minor units, 0 = none) for each of the five steps of a custom package (W19-R27) */
  customGuide(): Promise<number[]>
  deleteOpex(id: string): Promise<void>
  deleteOpexActual(id: string): Promise<void>
  deleteProspect(id: string): Promise<void>
  /** Platform admin: who the seller on the invoices is (W19-R16) */
  invoiceSettings(): Promise<InvoiceSeller>
  /** Platform admin: the platform's own running costs (W16-R9) */
  listOpex(): Promise<OpexList>
  listOpexActuals(): Promise<OpexActual[]>
  listPartners(): Promise<PlatformPartner[]>
  /** Platform admin: the prospect list, newest first, optionally one status */
  listProspects(status?: string): Promise<Prospect[]>
  listVouchers(): Promise<PlatformVoucher[]>
  /** Platform admin: end every cookie login of a person; returns how many were ended. */
  logoutUser(id: string): Promise<number>
  opexCsv(year: number): Promise<string>
  opexForecast(scenario: OpexScenarioName, months: number): Promise<OpexForecast>
  opexMonthly(year: number): Promise<OpexMonthly>
  opexRates(): Promise<OpexRate[]>
  /** Platform admin: the platform audit log, newest first; next_before is the cursor for the next page. */
  ownerAudit(query?: OwnerAuditQuery): Promise<{ items: OwnerAuditItem[]; next_before: string | null }>
  /** Platform admin: configuration and live checks of the platform's outside services (no secrets). */
  ownerHealth(): Promise<OwnerHealth>
  ownerOrganizations(): Promise<OwnerOrg[]>
  /** Platform admin: counts, signups per week and what needs attention. */
  ownerOverview(): Promise<OwnerOverview>
  /** Platform admin: what waits for a person (own-domain requests, help asked, support access granted, Google, failed squares). */
  ownerAttention(): Promise<OwnerAttentionList>
  ownerSquare(id: string): Promise<OwnerSquareDetail>
  /** Support access (ADR 089): active grants and requests; one square's grant; ask the owner; open a session (the one gate); end it. */
  supportOverview(): Promise<SupportOverview>
  supportSquare(id: string): Promise<SupportSquareState>
  supportRequest(id: string, note: string): Promise<void>
  supportStart(id: string): Promise<SupportSessionStart>
  supportEnd(sessionId: string): Promise<void>
  ownerSquares(): Promise<OwnerSquare[]>
  ownerSubscriptions(): Promise<OwnerSubscriptions>
  ownerUser(id: string): Promise<OwnerUserDetail>
  ownerUsers(): Promise<OwnerUser[]>
  partnerReport(id: string): Promise<PartnerReport>
  recordOpexActual(input: { item_id: string; month: string; amount_minor: number }): Promise<OpexActual>
  refreshOpexRates(): Promise<OpexRate[]>
  /** Platform admin: refund a first payment, a renewal or an Event pass inside the refund days (W12-R19, W13-R31). Money moves. No amount = all of it, with its effects;
   * an amount = a goodwill refund of part of it (nothing else changes). */
  refundOrder(orderId: string, amountMinor?: number): Promise<BillingOrder>
  saveCustomGuide(steps: number[]): Promise<number[]>
  saveInvoiceSettings(input: InvoiceSeller): Promise<InvoiceSeller>
  saveOpexAssumptions(input: OpexAssumptions): Promise<OpexAssumptions>
  saveVoucherSettings(input: VoucherSettings): Promise<VoucherSettings>
  /** Platform admin: agree a custom package with one square: its modules and one amount per period (W19-R20) */
  setCustomPackage(squareId: string, input: { modules: string[]; amount_minor: number; interval: 'month' | 'year' }): Promise<PlatformSquare>
  setOpexRate(code: 'NOK' | 'INR', rate: number): Promise<OpexRate[]>
  /** Platform admin: change a price (W14-R27). It applies to new orders; orders already made keep their amount. */
  setPrice(key: string, amountMinor: number): Promise<PlanPrice>
  /** Platform admin: mark Google sign-in of a square as enabled or back to requested. */
  setSquareGoogle(id: string, enabled: boolean, apply?: boolean): Promise<PlatformSquare>
  /** Platform admin: stop or resume serving a square's public site. */
  suspendSquare(id: string, suspended: boolean): Promise<PlatformSquare>
  /** Platform admin: set the square's sign-in redirect list at the provider again. */
  syncSquareAuth(id: string): Promise<void>
  updateOpex(id: string, input: Partial<OpexInput> & { clear?: string[] }): Promise<OpexItem>
  updatePartner(id: string, input: Partial<PartnerInput>): Promise<PlatformPartner>
  updateProspect(id: string, input: { status?: string; notes?: string }): Promise<Prospect>
  updateVoucher(id: string, input: Partial<VoucherInput> & { clear?: string[] }): Promise<PlatformVoucher>
  voucherRedemptions(id: string): Promise<VoucherRedemption[]>
  /** Platform admin: vouchers and partners (W14-R27, docs/reference/prices-and-vouchers.md) */
  voucherSettings(): Promise<VoucherSettings>
  /** Delete a square for good (its project at the provider too). The address is typed to confirm; force is for platform admins. */
  deleteSquare(id: string, confirmSlug: string, force?: boolean): Promise<void>
  /** The prices, as data (public). */
  getPrices(): Promise<PlanPrice[]>
  /** Modules plus the always-on parts and what each needs (the custom package form, W19-R24) */
  moduleCatalogue(): Promise<ModuleCatalogue>
  /** Provision a failed square again. */
  retrySquare(id: string): Promise<PlatformSquare>
  /** A square's own sending domain (ADR 091 and 095): read it, set up the owner's request at Resend, turn it down with a note, check it, remove it. */
  getMailDomain(id: string): Promise<MailDomain>
  approveMailDomain(id: string, input: { domain?: string; local_part?: string }): Promise<MailDomain>
  rejectMailDomain(id: string, note: string): Promise<MailDomain>
  checkMailDomain(id: string): Promise<MailDomain>
  removeMailDomain(id: string): Promise<MailDomain>
  /** A square's own website domain (ADR 098): read it (with a DNS look), activate the owner's request after adding the domain on the host, turn it down, remove it. */
  getSiteDomain(id: string): Promise<SiteDomain>
  activateSiteDomain(id: string, domain?: string): Promise<SiteDomain>
  /** Ask the host (Render) to look at the DNS again, then read the DNS and the host's answer. */
  checkSiteDomain(id: string): Promise<SiteDomain>
  rejectSiteDomain(id: string, note: string): Promise<SiteDomain>
  removeSiteDomain(id: string): Promise<SiteDomain>
}

export const adminApi: AdminApi = {
  checkSquare: (id) => call<{ ok: boolean; admins: number | null }>(`/squares/${id}/check`, post()),
  createOpex: (input) => call<OpexItem>('/opex/items', { method: 'POST', body: JSON.stringify(input) }),
  createPartner: (input) => call<PlatformPartner>('/partners', { method: 'POST', body: JSON.stringify(input) }),
  createVoucher: (input) => call<PlatformVoucher>('/vouchers', { method: 'POST', body: JSON.stringify(input) }),
  customGuide: async () => (await call<{ steps: number[] }>('/custom-guide')).steps,
  deleteOpex: async (id) => { await call(`/opex/items/${id}`, { method: 'DELETE' }) },
  deleteOpexActual: async (id) => { await call(`/opex/actuals/${id}`, { method: 'DELETE' }) },
  deleteProspect: async (id) => { await call(`/prospects/${id}`, { method: 'DELETE' }) },
  invoiceSettings: () => call<InvoiceSeller>('/invoice-settings'),
  listOpex: () => call<OpexList>('/opex/items'),
  listOpexActuals: async () => (await call<{ actuals: OpexActual[] }>('/opex/actuals')).actuals,
  listPartners: async () => (await call<{ items: PlatformPartner[] }>('/partners')).items,
  listProspects: async (status) => (await call<{ items: Prospect[] }>(`/prospects${status ? `?status=${encodeURIComponent(status)}` : ''}`)).items,
  listVouchers: async () => (await call<{ items: PlatformVoucher[] }>('/vouchers')).items,
  logoutUser: async (id) => (await call<{ revoked: number }>(`/users/${id}/logout-all`, post())).revoked,
  opexCsv: async (year) => {
    const r = await raw(`/opex/export.csv?year=${year}`).catch(() => { throw new ApiError(0, 'network_error', 'The server is not reachable') })
    if (!r.ok) throw await toError(r)
    return r.text()
  },
  opexForecast: (scenario, months) => call<OpexForecast>(`/opex/forecast?scenario=${scenario}&months=${months}`),
  opexMonthly: (year) => call<OpexMonthly>(`/opex/monthly?year=${year}`),
  opexRates: async () => (await call<{ rates: OpexRate[] }>('/opex/rates')).rates,
  ownerAudit: (query = {}) => {
    const qs = new URLSearchParams(Object.entries(query).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => [k, String(v)])).toString()
    return call<{ items: OwnerAuditItem[]; next_before: string | null }>(`/audit${qs ? `?${qs}` : ''}`)
  },
  ownerHealth: () => call<OwnerHealth>('/health'),
  ownerOrganizations: async () => (await call<{ items: OwnerOrg[] }>('/organizations')).items,
  ownerOverview: () => call<OwnerOverview>('/overview'),
  ownerAttention: () => call<OwnerAttentionList>('/attention'),
  ownerSquare: (id) => call<OwnerSquareDetail>(`/squares/${id}`),
  supportOverview: () => call<SupportOverview>('/support/overview'),
  supportSquare: (id) => call<SupportSquareState>(`/support/squares/${id}`),
  supportRequest: async (id, note) => { await call(`/support/squares/${id}/request`, post({ note })) },
  supportStart: (id) => call<SupportSessionStart>(`/support/squares/${id}/session`, post()),
  supportEnd: async (sessionId) => { await call(`/support/sessions/${sessionId}/end`, post()) },
  ownerSquares: async () => (await call<{ items: OwnerSquare[] }>('/squares')).items,
  ownerSubscriptions: () => call<OwnerSubscriptions>('/subscriptions'),
  ownerUser: (id) => call<OwnerUserDetail>(`/users/${id}`),
  ownerUsers: async () => (await call<{ items: OwnerUser[] }>('/users')).items,
  partnerReport: (id) => call<PartnerReport>(`/partners/${id}/report`),
  recordOpexActual: (input) => call<OpexActual>('/opex/actuals', { method: 'PUT', body: JSON.stringify(input) }),
  refreshOpexRates: async () => (await call<{ rates: OpexRate[] }>('/opex/rates/refresh', { method: 'POST' })).rates,
  refundOrder: (orderId, amountMinor) => call<BillingOrder>(`/billing/orders/${orderId}/refund`, post(amountMinor === undefined ? undefined : { amount_minor: amountMinor })),
  saveCustomGuide: async (steps) => (await call<{ steps: number[] }>('/custom-guide', { method: 'PUT', body: JSON.stringify({ steps }) })).steps,
  saveInvoiceSettings: (input) => call<InvoiceSeller>('/invoice-settings', { method: 'PUT', body: JSON.stringify(input) }),
  saveOpexAssumptions: (input) => call<OpexAssumptions>('/opex/assumptions', { method: 'PUT', body: JSON.stringify(input) }),
  saveVoucherSettings: (input) => call<VoucherSettings>('/voucher-settings', { method: 'PUT', body: JSON.stringify(input) }),
  setCustomPackage: (id, input) => call<PlatformSquare>(`/squares/${id}/custom-package`, { method: 'PUT', body: JSON.stringify(input) }),
  setOpexRate: async (code, rate) => (await call<{ rates: OpexRate[] }>('/opex/rates', { method: 'PUT', body: JSON.stringify({ code, rate }) })).rates,
  setPrice: (key, amountMinor) => call<PlanPrice>(`/prices/${encodeURIComponent(key)}`, { method: 'PUT', body: JSON.stringify({ amount_minor: amountMinor }) }),
  setSquareGoogle: (id, enabled, apply = false) => call<PlatformSquare>(`/squares/${id}/google`, post({ enabled, apply })),
  suspendSquare: (id, suspended) => call<PlatformSquare>(`/squares/${id}/suspend`, post({ suspended })),
  syncSquareAuth: async (id) => { await call(`/squares/${id}/sync-auth`, post()) },
  updateOpex: (id, input) => call<OpexItem>(`/opex/items/${id}`, { method: 'PATCH', body: JSON.stringify(input) }),
  updatePartner: (id, input) => call<PlatformPartner>(`/partners/${id}`, { method: 'PATCH', body: JSON.stringify(input) }),
  updateProspect: (id, input) => call<Prospect>(`/prospects/${id}`, { method: 'PATCH', body: JSON.stringify(input) }),
  updateVoucher: (id, input) => call<PlatformVoucher>(`/vouchers/${id}`, { method: 'PATCH', body: JSON.stringify(input) }),
  voucherRedemptions: async (id) => (await call<{ items: VoucherRedemption[] }>(`/vouchers/${id}/redemptions`)).items,
  voucherSettings: () => call<VoucherSettings>('/voucher-settings'),
  deleteSquare: async (id, confirmSlug, force = false) => { await call(`/squares/${id}`, { method: 'DELETE', body: JSON.stringify({ confirm_slug: confirmSlug, force }) }) },
  getPrices: async () => (await call<{ items: PlanPrice[] }>('/prices')).items,
  moduleCatalogue: () => call<ModuleCatalogue>('/modules'),
  retrySquare: (id) => call<PlatformSquare>(`/squares/${id}/retry`, post()),
  getMailDomain: (id) => call<MailDomain>(`/squares/${id}/mail-domain`),
  approveMailDomain: (id, input) => call<MailDomain>(`/squares/${id}/mail-domain/approve`, post(input)),
  rejectMailDomain: (id, note) => call<MailDomain>(`/squares/${id}/mail-domain/reject`, post({ note })),
  checkMailDomain: (id) => call<MailDomain>(`/squares/${id}/mail-domain/check`, post()),
  removeMailDomain: (id) => call<MailDomain>(`/squares/${id}/mail-domain`, { method: 'DELETE' }),
  getSiteDomain: (id) => call<SiteDomain>(`/squares/${id}/site-domain`),
  checkSiteDomain: (id) => call<SiteDomain>(`/squares/${id}/site-domain/check`, post()),
  activateSiteDomain: (id, domain) => call<SiteDomain>(`/squares/${id}/site-domain/activate`, post({ domain })),
  rejectSiteDomain: (id, note) => call<SiteDomain>(`/squares/${id}/site-domain/reject`, post({ note })),
  removeSiteDomain: (id) => call<SiteDomain>(`/squares/${id}/site-domain`, { method: 'DELETE' }),
}
