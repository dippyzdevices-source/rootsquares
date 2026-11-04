<script setup lang="ts">
import { moduleEnabled, type ModuleKey } from '../services/modules'
import { ref, onMounted } from 'vue'
import DefaultFrame from './DefaultFrame.vue'
import LayoutShell from '../layout-themes/LayoutShell.vue'
import { activeLayout } from '../layout-themes/layouts'
import NavIcon, { type NavIconName } from '../components/ui/NavIcon.vue'
import { fetchMyMember, fetchMyTaskAssignments } from '../services/memberApi'
import { fetchMyOrders } from '../services/ordersApi'
import { fetchMyMembershipPayments } from '../services/membershipPaymentsApi'

const allNavItems: { label: string; to: string; icon: NavIconName; countKey?: string; module?: ModuleKey }[] = [
  { label: 'Overview', to: '/member', icon: 'dashboard' },
  { label: 'Family', to: '/member/family', icon: 'users', countKey: 'family', module: 'memberships' },
  { label: 'My Tickets', to: '/member/tickets', icon: 'ticket', countKey: 'tickets', module: 'tickets' },
  { label: 'Volunteering', to: '/member/volunteering', icon: 'user-check', countKey: 'volunteering', module: 'volunteering' },
  { label: 'Payments', to: '/member/payments', icon: 'receipt', countKey: 'payments', module: 'payments' },
  { label: 'Settings', to: '/member/settings', icon: 'settings' },
]

// A module the owner turned off has no item (W8-R19).
const navItems = allNavItems.filter((item) => moduleEnabled(item.module))

// Mirrors AdminLayout.vue's own "quick counts" sidebar badges — one best-effort fetch per
// section, each failure independent (a failed one just leaves its badge hidden).
const counts = ref<Record<string, number>>({})

onMounted(async () => {
  try {
    if (!moduleEnabled('members')) throw new Error('no Members module')
    const profile = await fetchMyMember()
    counts.value.family = profile.family_members?.length ?? 0
  } catch {
    // Leave unset — the Family badge simply doesn't render.
  }

  let orderCount = 0
  try {
    if (!moduleEnabled('tickets')) throw new Error('no Tickets module')
    const orders = await fetchMyOrders()
    orderCount = orders.items.length
    counts.value.tickets = orderCount
  } catch {
    // Leave unset — the My Tickets badge simply doesn't render.
  }

  try {
    const membershipPayments = moduleEnabled('memberships') ? await fetchMyMembershipPayments() : []
    counts.value.payments = orderCount + membershipPayments.length
  } catch {
    // Leave unset — the Payments badge simply doesn't render.
  }

  try {
    if (!moduleEnabled('volunteering')) throw new Error('no Volunteering module')
    counts.value.volunteering = (await fetchMyTaskAssignments()).length
  } catch {
    // Leave unset — the Volunteering badge simply doesn't render.
  }
})

// A square on a layout theme gets that theme's header, navigation and footer here too (W10-R4); the default theme keeps the original frame.
const Frame = activeLayout ? LayoutShell : DefaultFrame
</script>

<template>
  <component :is="Frame">
    <div style="flex: 1; max-width: var(--ds-container-max); width: 100%; margin: 0 auto; padding: var(--ds-space-6) var(--ds-gutter)">
      <div class="ds-appshell">
        <aside class="ds-appshell__nav">
          <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow); margin-bottom: var(--ds-space-3)">My portal</p>
          <nav class="ds-appshell__links">
            <router-link
              v-for="item in navItems"
              :key="item.to"
              :to="item.to"
              class="ds-appshell__link"
              exact-active-class="ds-appshell__link-active"
            >
              <NavIcon :name="item.icon" class="ds-appshell__link-icon" />
              <span style="flex: 1">{{ item.label }}</span>
              <span v-if="item.countKey && counts[item.countKey] !== undefined" class="ds-appshell__link-count">
                {{ counts[item.countKey] }}
              </span>
            </router-link>
          </nav>
        </aside>

        <div style="min-width: 0">
          <router-view />
        </div>
      </div>
    </div>
  </component>
</template>
