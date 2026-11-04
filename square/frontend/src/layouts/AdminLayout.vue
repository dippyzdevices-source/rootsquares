<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import DefaultFrame from './DefaultFrame.vue'
import LayoutShell from '../layout-themes/LayoutShell.vue'
import { activeLayout } from '../layout-themes/layouts'
import NavIcon, { type NavIconName } from '../components/ui/NavIcon.vue'
import { fetchAdminEvents } from '../services/adminEventsApi'
import { fetchAdminMembers } from '../services/adminMembersApi'
import { fetchAdminMemberships } from '../services/adminMembershipsApi'
import { moduleEnabled, type ModuleKey } from '../services/modules'
import { squareProfile } from '../services/squareConfig'
import { formatEventDate } from '../utils/date'
import { fetchAdminTickets } from '../services/adminTicketsApi'
import { fetchAdminOrders } from '../services/adminOrdersApi'
import { fetchAdminPayments } from '../services/adminPaymentsApi'
import { fetchAdminAlbums } from '../services/adminGalleryApi'
import { fetchAdminNews } from '../services/adminNewsApi'
import { fetchAdminTestimonials } from '../services/adminTestimonialsApi'
import { fetchAdminUsers } from '../services/adminUsersApi'

// `sections`: extra path prefixes that also light the item up — for areas whose sub-pages (tab strips,
// edit forms) live under other URLs. Plain items still use exact matching, so flat siblings never
// light up together (the BCA-011 admin sidebar bug).
const allNavItems: { label: string; to: string; icon: NavIconName; countKey?: string; sections?: string[]; module?: ModuleKey; eventPassOnly?: boolean }[] = [
  { label: 'Dashboard', to: '/admin', icon: 'dashboard' },
  { label: 'Events', to: '/admin/events', icon: 'calendar', countKey: 'events', module: 'events' },
  { label: 'Members', to: '/admin/members', icon: 'users', countKey: 'members', sections: ['/admin/members', '/admin/membership-types'], module: 'members' },
  { label: 'Check-in', to: '/admin/checkin', icon: 'scan', module: 'checkin' },
  { label: 'Orders', to: '/admin/orders', icon: 'shopping-bag', countKey: 'orders', module: 'tickets' },
  { label: 'Payments', to: '/admin/payments', icon: 'banknote', countKey: 'payments', module: 'payments' },
  { label: 'Donations', to: '/admin/donations', icon: 'banknote', module: 'donations' },
  { label: 'Tickets', to: '/admin/tickets', icon: 'ticket', countKey: 'tickets', module: 'tickets' },
  { label: 'Accounting', to: '/admin/accounting', icon: 'calculator', module: 'accounting' },
  { label: 'Gallery', to: '/admin/gallery', icon: 'image', countKey: 'gallery', module: 'gallery' },
  { label: 'News', to: '/admin/news', icon: 'file-text', countKey: 'news', sections: ['/admin/news'], module: 'news' },
  { label: 'Messages', to: '/admin/messages', icon: 'mail', sections: ['/admin/messages'], module: 'messages' },
  { label: 'Newsletter', to: '/admin/newsletter', icon: 'mail', sections: ['/admin/newsletter'], module: 'newsletter' },
  { label: 'Testimonials', to: '/admin/testimonials', icon: 'message-square', countKey: 'testimonials', module: 'testimonials' },
  { label: 'Volunteers', to: '/admin/volunteers', icon: 'user-check', countKey: 'volunteers', module: 'checkin' },
  { label: 'Event wrap-up', to: '/admin/event-pass', icon: 'file-text', eventPassOnly: true },
  { label: 'Audit Log', to: '/admin/audit-log', icon: 'list' },
  { label: 'Settings', to: '/admin/content', icon: 'settings' },
]

// A module the owner turned off has no menu item (W8-R9).
// Without Memberships the Members area is a plain list of people (ADR 044).
// An Event pass in its archive (W11, ADR 044) is read-only: no door check-in, no volunteer access. The wrap-up page is only for a pass.
const eventPass = squareProfile.eventPass
const archive = eventPass?.phase === 'archive'
const navItems = allNavItems
  .filter((item) => moduleEnabled(item.module))
  .filter((item) => !item.eventPassOnly || eventPass !== null)
  .filter((item) => !(archive && item.module === 'checkin'))
  .map((item) => (item.to === '/admin/members' && !moduleEnabled('memberships') ? { ...item, label: 'People' } : item))

// Each entry is a best-effort total-item count for its section's sidebar badge — fetched
// once per admin-console visit, same "quick counts" pattern AdminDashboardView.vue already
// uses. A failed fetch just leaves that one key out (badge hidden), never blocks the rest.
const counts = ref<Record<string, number>>({})
const COUNT_MODULE: Record<string, ModuleKey | undefined> = { events: 'events', members: 'members', memberships: 'memberships', tickets: 'tickets', orders: 'tickets', payments: 'payments', gallery: 'gallery', news: 'news', testimonials: 'testimonials', volunteers: 'checkin' }

const route = useRoute()

function inSection(item: { sections?: string[] }): boolean {
  return !!item.sections?.some((prefix) => route.path === prefix || route.path.startsWith(`${prefix}/`))
}

onMounted(async () => {
  const allFetchers: [string, () => Promise<{ total: number }>][] = [
    ['events', () => fetchAdminEvents(1, 1)],
    ['members', () => fetchAdminMembers('', '', 1)],
    ['memberships', () => fetchAdminMemberships({ perPage: 1 })],
    ['tickets', () => fetchAdminTickets({ perPage: 1 })],
    ['orders', () => fetchAdminOrders({ perPage: 1 })],
    ['payments', () => fetchAdminPayments({ perPage: 1 })],
    ['gallery', () => fetchAdminAlbums(1)],
    ['news', () => fetchAdminNews(1)],
    ['testimonials', () => fetchAdminTestimonials(undefined, 1)],
    ['volunteers', () => fetchAdminUsers(undefined, 'volunteer', 1)],
  ]

  // Only the sections the square has are counted: a module that is off has no API (W8-R10).
  const fetchers = allFetchers.filter(([key]) => moduleEnabled(COUNT_MODULE[key]))
  await Promise.all(
    fetchers.map(async ([key, fetcher]) => {
      try {
        counts.value[key] = (await fetcher()).total
      } catch {
        // Leave this key unset — its nav badge simply doesn't render.
      }
    }),
  )
})

// A square on a layout theme gets that theme's header, navigation and footer here too (W10-R4); the default theme keeps the original frame.
const Frame = activeLayout ? LayoutShell : DefaultFrame
</script>

<template>
  <component :is="Frame">
    <div style="flex: 1; max-width: var(--ds-container-max); width: 100%; margin: 0 auto; padding: var(--ds-space-6) var(--ds-gutter)">
      <div class="ds-appshell">
        <aside class="ds-appshell__nav">
          <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow); margin-bottom: var(--ds-space-3)">Admin console</p>
          <nav class="ds-appshell__links">
            <router-link
              v-for="item in navItems"
              :key="item.to"
              :to="item.to"
              class="ds-appshell__link"
              :class="{ 'ds-appshell__link-active': inSection(item) }"
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

        <div class="admin-content" style="min-width: 0">
          <div v-if="archive" class="archive-note" role="status" data-testid="archive-note">
            <b>This event is over.</b> The site is a read-only archive: only you can sign in. Download your reports; everything is deleted after
            {{ formatEventDate(eventPass?.archiveUntil ?? '') }}.
            <router-link to="/admin/event-pass">Open the wrap-up</router-link>
          </div>
          <router-view />
        </div>
      </div>
    </div>
  </component>
</template>

<style scoped>
.archive-note {
  margin-bottom: var(--ds-space-5, 20px);
  padding: var(--ds-space-3, 12px) var(--ds-space-4, 16px);
  border: 1px solid var(--ds-border-default, currentColor);
  border-radius: var(--ds-radius-md, 6px);
  background: var(--ds-surface-sunken, transparent);
  font-size: var(--ds-text-sm, 0.875rem);
}
</style>

<style>
/* One compact type and spacing scale for the whole admin console (the public and member screens keep the larger one).
   Tokens are re-pointed here so every ds-* component inside the console follows. */
.admin-content {
  --ds-text-display-l: clamp(26px, 3vw, 34px);
  --ds-text-display-m: clamp(24px, 2.8vw, 30px);
  --ds-text-display-s: clamp(22px, 2.4vw, 28px);
  --ds-text-title: 22px;
  --ds-text-subtitle: 18px;
  --ds-text-body-l: 15px;
  --ds-text-body-m: 14px;
  --ds-text-body-s: 13px;
  --ds-text-caption: 12px;
  font-size: 14px;
}
.admin-content .ds-card { padding: 18px 20px; }
.admin-content .ds-table { font-size: 13.5px; }
.admin-content .ds-table th, .admin-content .ds-table td { padding: 9px 12px; }
/* Names and emails in table rows stay on one line instead of breaking mid-word in a squeezed column */
.admin-content .ds-table .ds-avatar-label-name { white-space: nowrap; overflow-wrap: normal; }
.admin-content .ds-table .ds-avatar-label-email { white-space: nowrap; overflow-wrap: normal; max-width: 260px; overflow: hidden; text-overflow: ellipsis; }
</style>
