// MOCK DATA for the platform v3 console screens (Settings, Support access, Owner console). Nothing here is real: people, addresses, figures
// and dates are invented placeholders (listed in MISSING.md). Names reuse the BCA Oslo demo tenant.
import { PLAN_PRICE_KR } from './placeholders'

// ---- Settings: users, invitations ----
export type Role = 'owner' | 'admin' | 'editor' | 'viewer'
export interface OrgUser { id: number; name: string; email: string; role: Role }
export interface Invitation { id: number; email: string; role: Exclude<Role, 'owner'>; sentDays: number; expiresDays: number }

export const orgUsers: OrgUser[] = [
  { id: 1, name: 'Sreya Chatterjee', email: 'president@bca-oslo.example', role: 'owner' },
  { id: 2, name: 'Debasish Ghosh', email: 'treasurer@bca-oslo.example', role: 'admin' },
  { id: 3, name: 'Moumita Das', email: 'secretary@bca-oslo.example', role: 'editor' },
  { id: 4, name: 'Rahul Mitra', email: 'youth@bca-oslo.example', role: 'viewer' },
]
export const invitations: Invitation[] = [
  { id: 1, email: 'jonas@bca-oslo.example', role: 'editor', sentDays: 3, expiresDays: 4 },
  { id: 2, email: 'elin.haugen-solheim@bca-oslo.example', role: 'viewer', sentDays: 0, expiresDays: 7 },
]

// ---- Support access: audit log (action text is an i18n key under sa.actions) ----
export interface AuditEntry { id: number; at: string; who: string; action: 'viewedOrders' | 'resentConfirmation' | 'changedAddress' | 'viewedDomain'; scope: 'orders' | 'settings' | 'content' }
export const auditLog: AuditEntry[] = [
  { id: 1, at: '2026-10-12T14:32', who: 'Anna K.', action: 'viewedOrders', scope: 'orders' },
  { id: 2, at: '2026-10-12T14:35', who: 'Anna K.', action: 'resentConfirmation', scope: 'orders' },
  { id: 3, at: '2026-10-12T14:41', who: 'Anna K.', action: 'changedAddress', scope: 'settings' },
  { id: 4, at: '2026-10-12T14:44', who: 'Anna K.', action: 'viewedDomain', scope: 'settings' },
]

// ---- Owner console ----
export type TenantStatus = 'trial' | 'active' | 'pastDue' | 'suspended'
export type PlanName = 'Small club' | 'Community' | 'Federation'
export interface OwnerTenant {
  id: string
  name: string
  address: string
  plan: PlanName
  status: TenantStatus
  hoursAgo: number // last activity
  members: number
  since: string // ISO date
  modules: boolean[] // events, tickets, membership, gallery and articles, accounting
  storageGb: number
  emailsMonth: number
  nextDate: string // renewal, next attempt or trial end (ISO)
}
export const ownerTenants: OwnerTenant[] = [
  { id: 'bca-oslo', name: 'BCA Oslo', address: 'bca-oslo.rootsquares.com', plan: 'Community', status: 'active', hoursAgo: 0.03, members: 40, since: '2026-05-04', modules: [true, true, true, true, true], storageGb: 1.2, emailsMonth: 640, nextDate: '2026-11-04' },
  { id: 'aland', name: 'Åland Kulturförening', address: 'aland.rootsquares.com', plan: 'Community', status: 'active', hoursAgo: 5, members: 212, since: '2026-03-12', modules: [true, true, true, false, true], storageGb: 2.1, emailsMonth: 1840, nextDate: '2026-11-12' },
  { id: 'bergen-tamil', name: 'Bergen Norwegian-Tamil School', address: 'bergentamil.no', plan: 'Small club', status: 'suspended', hoursAgo: 41 * 24, members: 48, since: '2026-06-02', modules: [true, false, true, false, false], storageGb: 0.4, emailsMonth: 12, nextDate: '2026-11-02' },
  { id: 'malmo', name: 'Malmö Polska Förening', address: 'malmo-polska.rootsquares.com', plan: 'Community', status: 'trial', hoursAgo: 24, members: 71, since: '2026-09-20', modules: [true, true, true, true, false], storageGb: 0.6, emailsMonth: 210, nextDate: '2026-11-15' },
  { id: 'kobenhavn', name: 'Københavns Urdu Klub', address: 'urduklub.dk', plan: 'Small club', status: 'pastDue', hoursAgo: 72, members: 33, since: '2026-02-08', modules: [true, true, true, false, false], storageGb: 0.9, emailsMonth: 95, nextDate: '2026-11-13' },
  { id: 'sikh', name: 'Nordic Sikh Federation', address: 'nordicsikh.rootsquares.com', plan: 'Federation', status: 'active', hoursAgo: 1, members: 402, since: '2026-01-15', modules: [true, true, true, true, true], storageGb: 3.8, emailsMonth: 4120, nextDate: '2026-11-18' },
  { id: 'helsinki', name: 'Helsinki Language Café', address: 'helsinki-cafe.rootsquares.com', plan: 'Small club', status: 'trial', hoursAgo: 4, members: 19, since: '2026-09-28', modules: [true, false, true, false, false], storageGb: 0.1, emailsMonth: 30, nextDate: '2026-11-15' },
  { id: 'hamburg', name: 'Hamburg Kerala Samajam', address: 'hamburg-kerala.de', plan: 'Community', status: 'active', hoursAgo: 28, members: 156, since: '2026-04-21', modules: [true, true, true, true, true], storageGb: 2.9, emailsMonth: 1500, nextDate: '2026-11-21' },
]
export const tenantStatuses: TenantStatus[] = ['trial', 'active', 'pastDue', 'suspended']
export const planLimits = { storageGb: 5, emailsMonth: 5000, membersCap: 400 }
export const planPrice = (p: PlanName) => PLAN_PRICE_KR[p === 'Small club' ? 'small' : p === 'Community' ? 'community' : 'federation']

export interface SupportRequest { id: number; key: 'payment' | 'domain'; when: string; by: string; status: 'awaiting' | 'closed' }
export const supportRequests: Record<string, SupportRequest[]> = {
  kobenhavn: [{ id: 1, key: 'payment', when: '2026-11-11', by: 'Ingrid H.', status: 'awaiting' }, { id: 2, key: 'domain', when: '2026-11-08', by: 'Anna K.', status: 'closed' }],
  hamburg: [{ id: 3, key: 'domain', when: '2026-10-30', by: 'Anna K.', status: 'closed' }],
}
