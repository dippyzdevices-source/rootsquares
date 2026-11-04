<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import PortalShell, { type NavItem } from '@rootsquares/ui/layouts/PortalShell.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { useStaffStore } from '@/stores/staff'
import { adminApi } from '@/adminApi'

// The admin console shell (ADR 083): the same frame as the customer portal, with the console's own menu and a brass band on top so nobody mistakes it.
// The design lists Tenants, Subscriptions, Support requests and Usage; the sections below are the ones that exist today (MISSING.md).
const { t } = useI18n()
const router = useRouter()
const staff = useStaffStore()
const { push } = useToast()
const route = useRoute()
// What waits for a person (W25-R33): the number beside "Needs attention", read on every page change and once a minute. A failed read leaves the old number.
const waiting = ref(0)
async function countWaiting() {
  try { waiting.value = (await adminApi.ownerAttention()).count } catch { /* the page itself shows errors; the badge just stays */ }
}
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { void countWaiting(); timer = setInterval(() => void countWaiting(), 60_000) })
onBeforeUnmount(() => clearInterval(timer))
watch(() => route.fullPath, () => void countWaiting())
// The nav path above every page, group and page as in the side bar (W25-R42); the square and person pages draw their own, with the back button.
const crumb = computed(() => {
  if (route.name === 'square' || route.name === 'person') return null
  if (route.name === 'security') return { group: t('own.nav.groupAccount'), label: t('adm.security.title') }
  const hit = nav.value.find((n) => (n.to === '/' ? route.path === '/' : route.path === n.to || route.path.startsWith(`${n.to}/`)))
  return hit && hit.group ? { group: hit.group, label: hit.label } : null
})
const nav = computed<NavItem[]>(() => [
  // grouped under small labels (W23-R83, `Sidebar Design.html`): twelve items scan faster in three groups
  { to: '/', label: t('own.nav.overview'), icon: 'home', exact: true, group: t('own.nav.groupPlatform') },
  { to: '/attention', label: t('own.nav.attention'), icon: 'bell', count: waiting.value, group: t('own.nav.groupPlatform') },
  { to: '/squares', label: t('own.nav.squares'), icon: 'globe', group: t('own.nav.groupPlatform') },
  { to: '/people', label: t('own.nav.people'), icon: 'users', group: t('own.nav.groupPlatform') },
  { to: '/organisations', label: t('own.nav.organisations'), icon: 'shield', group: t('own.nav.groupPlatform') },
  { to: '/audit', label: t('own.nav.audit'), icon: 'receipt', group: t('own.nav.groupPlatform') },
  { to: '/health', label: t('own.nav.health'), icon: 'chart', group: t('own.nav.groupPlatform') },
  { to: '/subscriptions', label: t('own.nav.subscriptions'), icon: 'card', group: t('own.nav.groupMoney') },
  { to: '/prices', label: t('own.nav.prices'), icon: 'receipt', group: t('own.nav.groupMoney') },
  { to: '/vouchers', label: t('own.nav.vouchers'), icon: 'card', group: t('own.nav.groupMoney') },
  { to: '/opex', label: t('own.nav.opex'), icon: 'chart', group: t('own.nav.groupMoney') },
  { to: '/prospects', label: t('own.nav.prospects'), icon: 'users', group: t('own.nav.groupSupport') },
  { to: '/support', label: t('own.nav.support'), icon: 'eye', group: t('own.nav.groupSupport') },
])
async function signOut() {
  await staff.logout()
  push(t('plat.nav.signedOut'), 'info')
  await router.push('/sign-in')
}
</script>

<template>
  <PortalShell tone="admin" :nav="nav" :area="t('portal.ownerArea')" :nav-label="t('own.nav.aria')" :user-name="staff.user?.name || staff.user?.email" :user-email="staff.user?.email" account-to="/security" @sign-out="signOut"><div v-if="crumb" class="oc-back"><nav :aria-label="t('own.nav.crumb')"><ol class="rs-crumbs"><li><span>{{ crumb.group }}</span><span aria-hidden="true">/</span></li><li aria-current="page">{{ crumb.label }}</li></ol></nav></div><RouterView /></PortalShell>
</template>
