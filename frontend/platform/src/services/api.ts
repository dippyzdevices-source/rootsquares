// Mock service layer: every function returns a promise of mock data, so a real API client can replace this file
// without changing components. No network calls.
import { events, members, committee, orders, ledger, monthly, invoices, tenants, photoLabels, ORG } from '@/mock/bca'
import type { BcaEvent, Member, CommitteeMember, Order, LedgerEntry, TenantRow } from '@/mock/bca'

const delay = <T>(value: T, ms = 120): Promise<T> => new Promise((resolve) => setTimeout(() => resolve(structuredClone(value)), ms))

export const getOrg = () => delay(ORG, 0)
export const getEvents = (): Promise<BcaEvent[]> => delay(events)
export const getEvent = (id: string): Promise<BcaEvent | undefined> => delay(events.find((e) => e.id === id))
export const getMembers = (): Promise<Member[]> => delay(members)
export const getCommittee = (): Promise<CommitteeMember[]> => delay(committee)
export const getOrders = (): Promise<Order[]> => delay(orders)
export const getLedger = (): Promise<LedgerEntry[]> => delay(ledger)
export const getMonthly = () => delay(monthly)
export const getInvoices = () => delay(invoices)
export const getTenants = (): Promise<TenantRow[]> => delay(tenants)
export const getPhotoLabels = () => delay(photoLabels, 0)

// Writes: succeed after a short delay and return what the server would return. Nothing is persisted.
export const markOrderPaid = (id: number, ref?: string) => delay({ id, status: 'paid' as const, ref }, 400)
export const createEvent = (e: Omit<BcaEvent, 'id'>) => delay({ ...e, id: e.title.toLowerCase().replace(/[^a-z0-9]+/g, '-') }, 400)
export const saveMember = (m: Omit<Member, 'id'>) => delay({ ...m, id: 1000 + Math.floor(Math.random() * 900) }, 300)
export const saveTheme = () => delay({ ok: true as const }, 500)
export const launchSite = () => delay({ ok: true as const }, 1500)
export const checkDomain = () => delay({ ok: true as const }, 1200)
export const placeOrder = (_eventId: string, total: number) => delay({ ok: true as const, orderId: 1043, total }, 700)
export const joinMembership = () => delay({ ok: true as const }, 700)

// Platform v3 console screens (Settings, Support access, Owner console). Same rules: promise-returning, mock data, nothing persisted.
import { auditLog, invitations, orgUsers, ownerTenants, supportRequests } from '@/mock/console'
import type { AuditEntry, Invitation, OrgUser, OwnerTenant, SupportRequest } from '@/mock/console'
export const getOrgUsers = (): Promise<OrgUser[]> => delay(orgUsers)
export const getInvitations = (): Promise<Invitation[]> => delay(invitations)
export const getAuditLog = (): Promise<AuditEntry[]> => delay(auditLog)
export const getOwnerTenants = (): Promise<OwnerTenant[]> => delay(ownerTenants)
export const getOwnerTenant = (id: string): Promise<OwnerTenant | undefined> => delay(ownerTenants.find((x) => x.id === id))
export const getSupportRequests = (tenantId: string): Promise<SupportRequest[]> => delay(supportRequests[tenantId] ?? [])
