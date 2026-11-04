import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { DEFAULT_TENANT_THEME, type ThemeMode } from '@rootsquares/ui/themes'
import { events as seedEvents, members as seedMembers, orders as seedOrders, committee as seedCommittee, ledger as seedLedger, type BcaEvent, type Member, type Order, type CommitteeMember, type LedgerEntry } from '@/mock/bca'

export interface Checkout { id: number; ref: string; eventId: string; eventTitle: string; eventDate: string; eventPlace: string; lines: { label: string; qty: number; price: number }[]; subtotal: number; fee: number; total: number; claimedPaid: boolean }
export type DomainMode = 'sub' | 'own'
export type DomainState = 'pending' | 'verifying' | 'live' | 'error'

// Shared state of the demo tenant: set by the onboarding wizard, read and edited by the console and the public site preview.
export const useTenantStore = defineStore('tenant', () => {
  const name = ref('BCA Oslo')
  const themeId = ref(DEFAULT_TENANT_THEME)
  const siteMode = ref<ThemeMode>('light')
  const modules = ref<string[]>(['events', 'tickets', 'membership', 'committee', 'accounting'])
  const domainMode = ref<DomainMode>('sub')
  const domain = ref('bca-oslo.rootsquares.com')
  const domainState = ref<DomainState>('live')
  const logoName = ref('')
  const accent = ref('')
  // Support-access grant created by the owner (ARCHITECTURE section 8): null = none. Mock: one 24-hour grant is active.
  const supportGrant = ref<{ until: string; scopes: string[]; who: string } | null>({ until: new Date(Date.now() + 24 * 3600_000).toISOString(), scopes: ['content', 'orders'], who: 'Anna K.' })

  const events = ref<BcaEvent[]>(structuredClone(seedEvents))
  const members = ref<Member[]>(structuredClone(seedMembers))
  const orders = ref<Order[]>(structuredClone(seedOrders))
  const committee = ref<CommitteeMember[]>(structuredClone(seedCommittee))
  const ledger = ref<LedgerEntry[]>(structuredClone(seedLedger))
  const published = ref(true)
  // The order being paid on the public site (manual Vipps step); the console shows the same order under Orders.
  const checkout = ref<Checkout | null>(null)
  const openOrders = computed(() => orders.value.filter((o) => o.status !== 'paid').length)

  function applyWizard(d: { name: string; themeId: string; modules: string[]; domainMode: DomainMode; domain: string; logoName: string; accent: string }) {
    name.value = d.name
    themeId.value = d.themeId
    modules.value = d.modules
    domainMode.value = d.domainMode
    domain.value = d.domain
    domainState.value = d.domainMode === 'own' ? 'pending' : 'live'
    logoName.value = d.logoName
    accent.value = d.accent
  }

  return { name, themeId, siteMode, modules, domainMode, domain, domainState, logoName, accent, supportGrant, events, members, orders, committee, ledger, published, checkout, openOrders, applyWizard }
})
