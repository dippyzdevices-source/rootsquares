// Real platform API client: cookies (httpOnly JWT) with credentials, the CSRF header on every request, problem+json errors,
// and one silent refresh when an access token has expired.
import { providerToken } from './authProvider'
import { ApiError, type ModuleInfo, type PlanPrice, type BillingOrder, type ModuleCatalogue, type PlatformSquare, type MailDomain, type SiteDomain } from '@rootsquares/ui/types/platformTypes'
import { type PortalAttentionList, type StarterSetInfo, type ModuleStatusAnswer, type SquareHealth, type Analytics, type SupportActivity, type SupportGrant, type SupportState, type Invoice, type PublicSquare, type SquareMe, type PlatformApi, type PlatformUser, type VoucherCheck } from '@/services/platformTypes'

const BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:5001').replace(/\/$/, '') + '/api/platform/v1'

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await providerToken() // a Supabase/Neon JWT when the user signed in through the provider (ADR 028), else the cookie session
  return fetch(BASE + path, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'rootsquares', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(init.headers ?? {}) },
  })
}

async function toError(r: Response): Promise<ApiError> {
  let body: { code?: string; detail?: string; title?: string; errors?: { loc: (string | number)[]; msg: string }[] } = {}
  try { body = await r.json() } catch { /* not JSON */ }
  return new ApiError(r.status, body.code ?? 'http_error', body.detail ?? body.title ?? `HTTP ${r.status}`, body.errors ?? [], body as Record<string, unknown>)
}

async function call<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  let r: Response
  try { r = await raw(path, init) } catch { throw new ApiError(0, 'network_error', 'The server is not reachable') }
  if (r.status === 401 && retry && !path.startsWith('/auth/') && !(await providerToken())) {
    const rr = await raw('/auth/refresh', { method: 'POST' }).catch(() => null)
    if (rr?.ok) return call<T>(path, init, false)
  }
  if (!r.ok) throw await toError(r)
  return (await r.json()) as T
}

// Public square data is read from many origins (square hosts) and needs no cookies: plain GETs without credentials.
async function publicCall<T>(path: string, headers: Record<string, string> = {}): Promise<T> {
  let r: Response
  try { r = await fetch(BASE + path, { headers }) } catch { throw new ApiError(0, 'network_error', 'The server is not reachable') }
  if (!r.ok) throw await toError(r)
  return (await r.json()) as T
}

const post = (body?: unknown): RequestInit => ({ method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const platformApi: PlatformApi = {
  me: () => call<PlatformUser>('/auth/me'),
  signup: (input) => call<PlatformUser>('/auth/signup', post(input)),
  login: (email, password) => call<PlatformUser>('/auth/login', post({ email, password })),
  logout: async () => { await call('/auth/logout', post()) },
  createOrganization: (name) => call<PlatformUser>('/organizations', post({ name })),
  listSquares: async () => (await call<{ items: PlatformSquare[] }>('/squares')).items,
  createSquare: (input) => call<PlatformSquare>('/squares', post(input)),
  getSquare: (id) => call<PlatformSquare>(`/squares/${id}`),
  deleteSquare: async (id, confirmSlug, force = false) => { await call(`/squares/${id}`, { method: 'DELETE', body: JSON.stringify({ confirm_slug: confirmSlug, force }) }) },
  exportMyData: async () => {
    let r: Response
    try { r = await raw('/me/export') } catch { throw new ApiError(0, 'network_error', 'The server is not reachable') }
    if (!r.ok) throw await toError(r)
    return r.blob()
  },
  deleteAccount: async (confirmEmail) => (await call<{ provider_account_removed: boolean }>('/me', { method: 'DELETE', body: JSON.stringify({ confirm_email: confirmEmail }) })).provider_account_removed,
  getSquareMe: (slug, squareToken) => publicCall<SquareMe>(`/public/squares/${encodeURIComponent(slug)}/me`, { Authorization: `Bearer ${squareToken}` }),
  getPublicSquare: (slug) => publicCall<PublicSquare>(`/public/squares/${encodeURIComponent(slug)}`),
  getPublicSquareByHost: (host) => publicCall<PublicSquare>(`/public/hosts/${encodeURIComponent(host)}`),
  uploadSquareLogo: (id, file, variant = 'light') => call<PlatformSquare>(`/squares/${id}/logo?variant=${variant}`, { method: 'POST', body: file, headers: { 'Content-Type': file.type } }),
  removeSquareLogo: (id, variant = 'light') => call<PlatformSquare>(`/squares/${id}/logo?variant=${variant}`, { method: 'DELETE' }),
  getModuleStatus: (id) => call<ModuleStatusAnswer>(`/squares/${id}/modules/status`),
  getSquareHealth: (id) => call<SquareHealth>(`/squares/${id}/health`),
  getSupport: (id) => call<SupportState>(`/squares/${id}/support`),
  getAnalytics: (id, days) => call<Analytics>(`/squares/${id}/analytics?days=${days}`),
  setAnalytics: (id, enabled) => call<Analytics>(`/squares/${id}/analytics`, { method: 'PUT', body: JSON.stringify({ enabled }) }),
  getSupportActivity: (id, page, perPage = 15) => call<SupportActivity>(`/squares/${id}/support/activity?page=${page}&per_page=${perPage}`),
  createSupportGrant: (id, input) => call<SupportGrant>(`/squares/${id}/support/grants`, { method: 'POST', body: JSON.stringify(input) }),
  revokeSupport: (id) => call<SupportState>(`/squares/${id}/support/revoke`, { method: 'POST' }),
  setRunningPlan: (id, plan) => call<PlatformSquare>(`/squares/${id}/running-plan`, { method: 'PUT', body: JSON.stringify({ running_plan: plan }) }),
  changePlan: (id, plan) => call<PlatformSquare>(`/squares/${id}/billing/plan-change`, { method: 'POST', body: JSON.stringify({ plan }) }),
  getPrices: async () => (await call<{ items: PlanPrice[] }>('/prices')).items,
  voucherPreview: (input) => call<VoucherCheck>('/billing/voucher-preview', { method: 'POST', body: JSON.stringify(input) }),
  voucherCheck: (id, input) => call<VoucherCheck>(`/squares/${id}/billing/voucher-check`, { method: 'POST', body: JSON.stringify(input) }),
  submitProspect: async (input) => { await call('/prospects', { method: 'POST', body: JSON.stringify(input) }) },
  getTaxRates: async () => (await call<{ tax_rates?: Record<string, number> }>('/prices')).tax_rates ?? {},
  confirmEventPassExport: (id) => call<PlatformSquare>(`/squares/${id}/event-pass/confirm-export`, { method: 'POST' }),
  startCheckout: (id, input) => call<{ order_id: string; url: string }>(`/squares/${id}/billing/checkout`, { method: 'POST', body: JSON.stringify(input) }),
  getOrder: (orderId) => call<BillingOrder>(`/billing/orders/${orderId}`),
  getInvoice: (orderId) => call<Invoice>(`/billing/orders/${orderId}/invoice`),
  confirmOrder: (id, orderId) => call<BillingOrder>(`/squares/${id}/billing/orders/${orderId}/confirm`, { method: 'POST' }),
  listOrders: async (id) => (await call<{ items: BillingOrder[] }>(`/squares/${id}/billing/orders`)).items,
  fakeConfirm: (orderId, outcome) => call<BillingOrder>(`/billing/orders/${orderId}/fake-confirm`, { method: 'POST', body: JSON.stringify({ outcome }) }),
  setBillingInterval: (id, interval) => call<PlatformSquare>(`/squares/${id}/billing-interval`, { method: 'PUT', body: JSON.stringify({ interval }) }),
  billingPortal: (id) => call<{ url: string }>(`/squares/${id}/billing/portal`, { method: 'POST' }),
  cancelRenewal: (id) => call<PlatformSquare>(`/squares/${id}/billing/cancel-renewal`, { method: 'POST' }),
  resumeRenewal: (id) => call<PlatformSquare>(`/squares/${id}/billing/resume-renewal`, { method: 'POST' }),
  listModules: async () => (await call<{ items: ModuleInfo[] }>('/modules')).items,
  moduleCatalogue: () => call<ModuleCatalogue>('/modules'),
  listStarterSets: async () => (await call<{ items: StarterSetInfo[] }>('/starter-sets')).items,
  getSiteDomain: (id) => call<SiteDomain>(`/squares/${id}/site-domain`),
  requestSiteDomain: (id, domain) => call<SiteDomain>(`/squares/${id}/site-domain/request`, { method: 'POST', body: JSON.stringify({ domain }) }),
  withdrawSiteDomainRequest: (id) => call<SiteDomain>(`/squares/${id}/site-domain/request`, { method: 'DELETE' }),
  askSiteDomainHelp: (id) => call<SiteDomain>(`/squares/${id}/site-domain/help`, { method: 'POST' }),
  checkSiteDomain: (id) => call<SiteDomain>(`/squares/${id}/site-domain/check`, { method: 'POST' }),
  removeSiteDomain: (id) => call<SiteDomain>(`/squares/${id}/site-domain`, { method: 'DELETE' }),
  getMailDomain: (id) => call<MailDomain>(`/squares/${id}/mail-domain`),
  requestMailDomain: (id, input) => call<MailDomain>(`/squares/${id}/mail-domain/request`, { method: 'POST', body: JSON.stringify(input) }),
  withdrawMailDomainRequest: (id) => call<MailDomain>(`/squares/${id}/mail-domain/request`, { method: 'DELETE' }),
  setMailFromName: (id, localPart) => call<MailDomain>(`/squares/${id}/mail-domain/name`, { method: 'PUT', body: JSON.stringify({ local_part: localPart }) }),
  sendMailDomainInstructions: (id, to) => call<MailDomain>(`/squares/${id}/mail-domain/instructions`, { method: 'POST', body: JSON.stringify({ to }) }),
  askMailDomainHelp: (id) => call<MailDomain>(`/squares/${id}/mail-domain/help`, { method: 'POST' }),
  getAttention: () => call<PortalAttentionList>('/attention'),
  checkMailDomain: (id) => call<MailDomain>(`/squares/${id}/mail-domain/check`, { method: 'POST' }),
  removeMailDomain: (id) => call<MailDomain>(`/squares/${id}/mail-domain`, { method: 'DELETE' }),
  setMailContact: (id, email) => call<PlatformSquare>(`/squares/${id}/mail-contact`, { method: 'PUT', body: JSON.stringify({ email }) }),
  setSquareTheme: (id, themeId) => call<PlatformSquare>(`/squares/${id}/theme`, { method: 'PUT', body: JSON.stringify({ theme_id: themeId }) }),
  setSquareLook: (id, look) => call<PlatformSquare>(`/squares/${id}/theme`, { method: 'PUT', body: JSON.stringify({ overrides: look && (look.colors || look.colors_dark || look.fonts || look.spinners?.length || (look.shape && Object.keys(look.shape).length) || (look.feel && Object.keys(look.feel).length) || look.type) ? look : null }) }),
  saveLookDraft: (id, look, options = {}) => call<PlatformSquare>(`/squares/${id}/theme/draft`, { method: 'PUT', body: JSON.stringify({ look, ...(options.themeId ? { theme_id: options.themeId } : {}), ...(options.passcode !== undefined ? { passcode: options.passcode } : {}), renew_link: !!options.renew }) }),
  saveLookSeasons: (id, seasons) => call<PlatformSquare>(`/squares/${id}/theme/seasons`, { method: 'PUT', body: JSON.stringify({ seasons }) }),
  removeLookDraft: (id) => call<PlatformSquare>(`/squares/${id}/theme/draft`, { method: 'DELETE' }),
  publishLookDraft: (id) => call<PlatformSquare>(`/squares/${id}/theme/draft/publish`, post()),
  setSquareModules: (id, modules) => call<PlatformSquare>(`/squares/${id}/modules`, { method: 'PUT', body: JSON.stringify({ modules }) }),
  retrySquare: (id) => call<PlatformSquare>(`/squares/${id}/retry`, post()),

}
