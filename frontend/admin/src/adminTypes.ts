// The types of the staff API that only the admin application uses (ADR 084 stage 3d); the shared ones are in @rootsquares/ui/types/platformTypes.
import type { SquareStatus, BillingOrder, PlatformSquare } from '@rootsquares/ui/types/platformTypes'

/** How codes combine on one payment (W15-R19): best = only the best code counts, sequential = one after the other, additive = added together */
export type OpexCadence = 'monthly' | 'quarterly' | 'yearly' | 'one_off'
/** One running cost of the platform (W16-R9, docs/plans/opex-plan.md); amounts in US dollar cents. */
export interface OpexInput { name: string; category: string; amount_minor: number; cadence: OpexCadence; start_on: string; end_on?: string | null; annual_increase_pct: number; vendor?: string | null; note?: string | null; cost_type?: 'fixed' | 'variable'; variable_bp?: number; variable_fixed_minor?: number }
export interface OpexItem extends OpexInput { id: string; currency: string; created_at: string }
export interface OpexList { items: OpexItem[]; categories: string[] }
export type OpexScenarioName = 'low' | 'base' | 'high'
export interface OpexScenario { new_per_month: number; churn_pct: number; revenue_per_square_minor: number | null }
export interface OpexAssumptions { opening_cash_minor: number; scenarios: Record<OpexScenarioName, OpexScenario> }
export interface OpexForecast {
  scenario: OpexScenarioName; currency: string
  months: { month: string; cost: number; revenue: number; net: number; cash: number }[]
  actuals: { month: string; revenue: number }[]
  break_even: string | null; runway_months: number | null; total_cost: number; total_revenue: number
  renewing_monthly: number; paying_squares: number; assumptions: OpexAssumptions; revenue_per_square_used: number
}
export interface OpexRate { code: 'NOK' | 'INR'; rate: number; date: string; source: 'frankfurter' | 'manual' }
export interface OpexActual { id: string; item_id: string; item_name: string; month: string; amount_minor: number }
export interface OpexMonthly { year: number; planned_totals: number[]; currency: string; categories: { name: string; months: number[]; total: number }[]; totals: number[]; total: number; previous_totals: number[]; previous_total: number }
export interface VoucherSettings { mode: 'best' | 'sequential' | 'additive'; max_codes: number }
export interface VoucherRedemption { order_id: string; paid_at: string | null; square_name: string; organization_name: string; kind: string; list_minor: number; discount_minor: number; paid_minor: number }
export interface PartnerInput { name: string; email: string | null; commission_percent: number; active: boolean }
export interface PlatformPartner extends PartnerInput { id: string; created_at: string; vouchers: number }
export interface PartnerReport {
  partner: PlatformPartner; uses: number; revenue_minor: number; discount_minor: number; commission_minor: number
  lines: { code: string; uses: number; revenue_minor: number; discount_minor: number; commission_minor: number }[]
}
export interface OwnerSquare extends PlatformSquare { owner_email: string | null; organization_name: string; suspended_at: string | null }
export interface OwnerSquareDetail extends OwnerSquare { provider: string | null; provider_project_ref: string | null; dashboard_url: string | null; billing_country?: string | null; timeline: { at: string; action: string }[]; orders: (BillingOrder & { refundable: boolean; refundable_minor?: number })[] }
export interface SubsCount { key: string; count: number; price_minor: number }
export interface SubsUpcoming { square_id: string; name: string; slug: string; state: 'trial' | 'unpaid' | 'renewing' | 'ending' | 'failed' | 'asleep' | 'paid' | 'expired'; paid_until: string | null; next_minor: number; package: string }
/** Money and plan state across squares for the owner console (W12-R20); USD minor units. */
export interface OwnerSubscriptions { mrr_minor: number; paid_30d_minor: number; paying: number; trial: number; failed: number; asleep: number; packages: SubsCount[]; running: SubsCount[]; upcoming: SubsUpcoming[] }
export interface OwnerAttention { kind: 'failed' | 'stuck' | 'google_requested' | 'mail_domain_requested' | 'mail_domain_help' | 'site_domain_requested' | 'site_domain_help' | 'support_granted'; square_id: string; name: string; slug: string; detail: string | null; since: string }
/** What waits for a person (W25-R33): the "Needs attention" page and the badge in the side bar. */
export interface OwnerAttentionList { items: OwnerAttention[]; count: number }
export interface OwnerOverview {
  squares_total: number; squares_ready: number; squares_provisioning: number; squares_awaiting_payment?: number; squares_failed: number
  users_total: number; organizations_total: number
  weeks: { week_start: string; users: number; squares: number }[]
  attention: OwnerAttention[]
}
export interface OwnerSquareRef { id: string; name: string; slug: string; status: SquareStatus; awaiting_payment?: boolean }
export interface OwnerUser { id: string; email: string; name: string; sign_in: string; organizations: number; active_sessions: number; created_at: string }
export interface OwnerUserDetail extends OwnerUser { orgs: { id: string; name: string; role: string; squares: OwnerSquareRef[] }[] }
export interface OwnerOrg { id: string; name: string; owner_email: string | null; members: number; created_at: string; squares: OwnerSquareRef[] }
export interface OwnerAuditItem { id: string; at: string; action: string; entity: string; entity_id: string; actor_id: string | null; actor_email: string | null; actor_kind?: 'user' | 'staff' | null; request_id: string | null; data: Record<string, unknown> }
export interface OwnerAuditQuery { action_prefix?: string; square_id?: string; actor_id?: string; before?: string; limit?: number }
export interface OwnerHealth { environment: Record<string, string>; checks: { id: string; status: 'ok' | 'warn' | 'fail' | 'off'; detail: string }[] }

// Support access (ADR 089, W23-R68): what staff see of a square's grant, never the owner's note or any content.
export type SupportScope = 'content' | 'settings' | 'health' | 'members'
export interface SupportSquareState { square_id: string; square_name: string; domain: string; active: boolean; scopes: SupportScope[]; allow_changes: boolean; expires_at: string | null }
export interface SupportOverviewRow { square_id: string; square_name: string; domain: string; scopes: SupportScope[]; allow_changes: boolean; expires_at: string | null; open_sessions: number }
export interface SupportOverviewRequest { square_id: string; square_name: string; staff_name: string; note: string; created_at: string; answered_at: string | null }
export interface SupportOverview { active: SupportOverviewRow[]; requests: SupportOverviewRequest[] }
export interface SupportSessionStart { session_id: string; token: string; token_expires_at: string; grant_expires_at: string; domain: string; scopes: SupportScope[]; allow_changes: boolean }
