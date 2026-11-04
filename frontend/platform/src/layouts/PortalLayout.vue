<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import PortalShell, { type NavItem } from '@rootsquares/ui/layouts/PortalShell.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { useAuthStore } from '@/stores/auth'
import { useAttention } from '@/features/portal/useAttention'

// Platform portal (the square owner's side of rootsquares; NOT the square's own admin). Inside a square the nav is the seven items of design v4:
// Dashboard, Theme, Modules, Domain, Billing, Settings, Support access. Outside a square (list of squares, account, create) it lists the owner's own pages.
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { push } = useToast()
const id = computed(() => (typeof route.params.id === 'string' ? route.params.id : ''))
// What waits for the owner (W25-R35): the number beside "Squares" (all squares) or "Dashboard" (this square). Read on every page change and once a minute.
const { items: waiting, refresh } = useAttention()
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { void refresh(); timer = setInterval(() => void refresh(), 60_000) })
onBeforeUnmount(() => clearInterval(timer))
watch(() => route.fullPath, () => void refresh())
const nav = computed<NavItem[]>(() => {
  if (id.value) {
    const b = `/squares/${id.value}`
    return [
      { to: b, label: t('portal.nav.dashboard'), icon: 'home', exact: true, count: waiting.value.filter((a) => a.square_id === id.value).length },
      { to: `${b}/theme`, label: t('portal.nav.theme'), icon: 'palette' },
      { to: `${b}/modules`, label: t('portal.nav.modules'), icon: 'grid' },
      { to: `${b}/health`, label: t('portal.nav.health'), icon: 'check' },
      { to: `${b}/analytics`, label: t('portal.nav.analytics'), icon: 'chart' },
      { to: `${b}/domain`, label: t('portal.nav.domain'), icon: 'globe' },
      { to: `${b}/billing`, label: t('portal.nav.billing'), icon: 'card' },
      { to: `${b}/payments`, label: t('portal.nav.payments'), icon: 'receipt' },
      { to: `${b}/settings`, label: t('portal.nav.settings'), icon: 'sliders' },
      { to: `${b}/support`, label: t('portal.nav.support'), icon: 'life' },
    ]
  }
  const list: NavItem[] = [
    { to: '/dashboard', label: t('portal.nav.squares'), icon: 'home', exact: true, count: waiting.value.length },
    { to: '/squares/new', label: t('portal.nav.newSquare'), icon: 'plus', exact: true },
    { to: '/account', label: t('portal.nav.account'), icon: 'users', exact: true },
  ]
  return list
})
// Who is signed in, under the name in the header (W26-R28): the organisation, or how many when there are several.
const orgLine = computed(() => {
  const o = auth.user?.organizations ?? []
  return o.length === 1 ? o[0]!.name : o.length > 1 ? t('plat.account.orgCount', { n: o.length }) : ''
})
async function signOut() {
  await auth.logout()
  push(t('plat.nav.signedOut'), 'info')
  await router.push('/')
}
</script>

<template>
  <PortalShell :nav="nav" :area="t('portal.area')" :eyebrow="id ? t('portal.eyebrowSquare') : t('portal.eyebrowAccount')" :nav-label="t('portal.navLabel')" :user-name="auth.user?.name || auth.user?.email" :user-email="auth.user?.email" :user-sub="orgLine" account-to="/account" @sign-out="signOut"><RouterView /></PortalShell>
</template>
