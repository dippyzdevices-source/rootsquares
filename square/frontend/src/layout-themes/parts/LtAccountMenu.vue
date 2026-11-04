<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import AccountMenu, { type AccountMenuItem } from '../../components/ui/AccountMenu.vue'
import { useLookup } from '../../composables/useLookup'
import { moduleEnabled, type ModuleKey } from '../../services/modules'
import { useAuthStore } from '../../stores/auth'
import { cta } from '../useSiteLayout'
import LtButton from './LtButton.vue'

// The default header's sign-in area for the themed shells (W10-R4, generic since W10-R6): a visitor sees Login (and the join button unless `join` is false); someone signed in sees the account menu
// (avatar and name; My portal, tickets, family, payments, settings, Admin console, Check-in, Sign out), the same items as the default header.
const props = withDefaults(defineProps<{ join?: boolean }>(), { join: true })
const auth = useAuthStore()
const router = useRouter()
const { label: roleLabel } = useLookup('user_role')
const membershipsOn = moduleEnabled('memberships')
const name = computed(() => auth.displayName ?? 'My Account')
const shortName = computed(() => (auth.displayName ? auth.displayName.split(' ')[0]! : 'My Account'))
const meta = computed(() => (auth.user ? roleLabel(auth.user.role) : null))

const items = computed<AccountMenuItem[]>(() => {
  const portal: (AccountMenuItem & { module?: ModuleKey })[] = [
    { id: 'dashboard', label: 'My portal', to: '/member', icon: 'dashboard' },
    { id: 'tickets', label: 'My tickets', to: '/member/tickets', icon: 'ticket', module: 'tickets' },
    { id: 'family', label: 'Family', to: '/member/family', icon: 'users', module: 'memberships' },
    { id: 'payments', label: 'Payments', to: '/member/payments', icon: 'receipt', module: 'payments' },
    { id: 'settings', label: 'Settings', to: '/member/settings', icon: 'settings' },
  ]
  const list: AccountMenuItem[] = portal.filter((item) => moduleEnabled(item.module))
  if (auth.isAdmin || auth.isVolunteer) list.push({ id: 'chrome-divider', label: '', divider: true })
  if (auth.isAdmin) list.push({ id: 'admin', label: 'Admin console', to: '/admin', icon: 'shield' })
  if ((auth.isAdmin || auth.isVolunteer) && moduleEnabled('checkin')) list.push({ id: 'checkin', label: 'Check-in', to: '/checkin', icon: 'scan' })
  list.push({ id: 'signout-divider', label: '', divider: true })
  list.push({ id: 'signout', label: 'Sign out', icon: 'log-out', tone: 'danger' })
  return list
})

async function select(id: string) {
  if (id !== 'signout') return
  await auth.signOut()
  router.push('/')
}
</script>

<template>
  <span class="lt-acctmenu">
    <template v-if="!auth.isAuthenticated">
      <router-link to="/login" class="lt-acct-login">Login</router-link>
      <LtButton v-if="props.join && membershipsOn" :to="cta.to" class="lt-es-join">{{ cta.label }}</LtButton>
    </template>
    <AccountMenu v-else :name="name" :short-name="shortName" :email="auth.user?.email ?? null" :avatar-url="auth.avatarUrl" :meta="meta" :items="items" @select="select" />
  </span>
</template>
