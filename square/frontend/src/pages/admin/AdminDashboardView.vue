<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { moduleEnabled } from '../../services/modules'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import GettingStartedCard from '../../components/GettingStartedCard.vue'
import { fetchAdminEvents, type AdminEvent } from '../../services/adminEventsApi'
import { fetchAdminMembers } from '../../services/adminMembersApi'
import { fetchAdminMemberships } from '../../services/adminMembershipsApi'
import { fetchAdminOrders, type AdminOrder } from '../../services/adminOrdersApi'
import { fetchAdminTestimonials } from '../../services/adminTestimonialsApi'
import { fetchReportsSummary, type ReportsSummary } from '../../services/adminReportsApi'
import { fetchEventAccountingSummary, type AccountingEventSummary } from '../../services/adminAccountingApi'
import { useAuthStore } from '../../stores/auth'
import { useLookup } from '../../composables/useLookup'
import { eventPhase, EVENT_PHASE_BADGE, EVENT_PHASE_LABEL } from '../../utils/eventPhase'
import { formatEventDate } from '../../utils/date'
import { formatPriceGrouped, formatPriceRoundedGrouped } from '../../utils/money'
import { humanize } from '../../utils/formatEnum'

const auth = useAuthStore()
const { label: orderStatusLabel } = useLookup('payment_status')

const eventCount = ref<number | null>(null)
const memberCount = ref<number | null>(null)
const ticketsOn = moduleEnabled('tickets') // W8-R29
const eventsOn = moduleEnabled('events') // W8-R28
const membershipsOn = moduleEnabled('memberships')
const pendingMembershipCount = ref<number | null>(null)
const pendingOrderCount = ref<number | null>(null)
const pendingTestimonialCount = ref<number | null>(null)
const summary = ref<ReportsSummary | null>(null)
const latestEvent = ref<AdminEvent | null>(null)
const eventSummary = ref<AccountingEventSummary | null>(null)
const recentOrders = ref<AdminOrder[]>([])

// --- greeting -------------------------------------------------------------------------------
const greeting = computed(() => {
  const hour = new Date().getHours()
  const part = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'
  const name = auth.displayName?.split(' ')[0] ?? auth.user?.email?.split('@')[0]
  return name ? `Good ${part}, ${name}` : `Good ${part}`
})

// --- customise: which widgets show (kept per browser, a convenience only) -------------------
const WIDGETS = [
  { key: 'todo', title: 'Needs your attention', hint: 'Action queue: the reason to open the dashboard' },
  { key: 'kpi', title: 'Key numbers', hint: 'Revenue, tickets, paid orders, active members' },
  { key: 'event', title: 'Latest event', hint: 'Net revenue, tickets, check-in at a glance' },
  { key: 'orders', title: 'Orders by status', hint: 'Only useful when pending or rejected is rising' },
  { key: 'recent', title: 'Latest orders', hint: 'Quick sanity check of live sales' },
  { key: 'members', title: 'Membership', hint: 'Active members by type' },
] as const
type WidgetKey = (typeof WIDGETS)[number]['key']
const STORAGE_KEY = 'admin-dashboard-widgets-v1'

function loadWidgetState(): Partial<Record<WidgetKey, boolean>> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Partial<Record<WidgetKey, boolean>>
  } catch {
    return {}
  }
}
const widgetState = ref(loadWidgetState())
const isShown = (key: WidgetKey) => widgetState.value[key] !== false
function setShown(key: WidgetKey, shown: boolean) {
  widgetState.value = { ...widgetState.value, [key]: shown }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(widgetState.value))
  } catch {
    // private mode / blocked storage: the choice just lasts until the page is reloaded
  }
}
const customiseOpen = ref(false)

// --- numbers --------------------------------------------------------------------------------
const orderStatuses = computed(() => summary.value?.orders_by_status ?? {})
const totalOrders = computed(() => Object.values(orderStatuses.value).reduce((a, b) => a + b, 0))
const paidOrders = computed(() => orderStatuses.value.paid ?? 0)
const successRate = computed(() => (totalOrders.value ? Math.round((paidOrders.value / totalOrders.value) * 100) : 0))
const pendingCount = computed(() => orderStatuses.value.pending ?? 0)
const pendingVerificationCount = computed(() => orderStatuses.value.pending_verification ?? 0)

const activeByType = computed(() =>
  Object.entries(summary.value?.memberships_active_by_type ?? {}).sort((a, b) => b[1] - a[1]),
)
const activeMembers = computed(() => summary.value?.memberships_by_status?.active ?? 0)
// Members whose latest membership is expired - the same filter the Members list applies, so the count matches what "View" shows.
const expiredMembers = ref(0)

const STATUS_COLOUR: Record<string, string> = {
  paid: 'var(--ds-status-success)',
  rejected: 'var(--ds-status-danger)',
  failed: 'var(--ds-status-danger)',
  cancelled: 'var(--ds-text-faint)',
  pending: 'var(--ds-status-warning)',
  pending_verification: 'var(--ds-status-info)',
}
const orderSegments = computed(() =>
  Object.entries(orderStatuses.value)
    .sort((a, b) => b[1] - a[1])
    .map(([status, count]) => ({
      status,
      count,
      colour: STATUS_COLOUR[status] ?? 'var(--ds-border-strong)',
      width: totalOrders.value ? (count / totalOrders.value) * 100 : 0,
    })),
)

const phase = computed(() => (latestEvent.value ? eventPhase(latestEvent.value) : null))
const couponTickets = computed(() => (eventSummary.value?.coupon_usage ?? []).reduce((n, c) => n + c.tickets_count, 0))
const couponDiscount = computed(() => (eventSummary.value?.coupon_usage ?? []).reduce((n, c) => n + c.discount_total, 0))
const couponGross = computed(() => (eventSummary.value?.coupon_usage ?? []).reduce((n, c) => n + c.gross_total, 0))
const checkinRate = computed(() => {
  const s = eventSummary.value
  return s && s.tickets_expected ? Math.round((s.tickets_checked_in / s.tickets_expected) * 100) : 0
})
const couponShare = computed(() => (couponGross.value ? Math.round((couponDiscount.value / couponGross.value) * 100) : 0))

// "Needs your attention": only rows that have something to do (the check-in row is information)
const attentionCount = computed(
  () =>
    (pendingOrderCount.value ?? 0) +
    (pendingMembershipCount.value ?? 0) +
    (pendingTestimonialCount.value ?? 0) +
    expiredMembers.value,
)
const showCheckinRow = computed(
  () => !!latestEvent.value && !!eventSummary.value && eventSummary.value.tickets_expected > 0 && phase.value !== 'draft',
)

function orderSubtitle(order: AdminOrder): string {
  const parts = [order.order_number]
  if (order.coupon_code) parts.push(`Coupon ${order.coupon_code}`)
  parts.push(formatEventDate(order.created_at))
  return parts.join(' · ')
}

onMounted(async () => {
  const [events, members, memberships, orders, latest, expired] = await Promise.all([
    eventsOn ? fetchAdminEvents(1, 1) : Promise.resolve(null),
    membershipsOn ? fetchAdminMembers('', '', 1) : Promise.resolve(null),
    membershipsOn ? fetchAdminMemberships({ status: 'pending', perPage: 1 }) : Promise.resolve(null),
    ticketsOn ? fetchAdminOrders({ paymentStatus: 'pending,pending_verification', perPage: 1 }) : Promise.resolve(null),
    ticketsOn ? fetchAdminOrders({ perPage: 4 }).catch(() => null) : Promise.resolve(null),
    membershipsOn ? fetchAdminMembers('', '', 1, ['expired']).catch(() => null) : Promise.resolve(null),
  ])
  // Members, memberships, orders and events are asked for only in a square that has them (W8-R19)
  eventCount.value = events?.total ?? null
  memberCount.value = members?.total ?? null
  expiredMembers.value = expired?.total ?? 0
  pendingMembershipCount.value = memberships?.total ?? null
  pendingOrderCount.value = orders?.total ?? null
  recentOrders.value = latest?.items ?? []
  latestEvent.value = events?.items?.[0] ?? null

  // Secondary stats load side by side (each is slow on a remote database); the page works without any of them.
  await Promise.all([
    moduleEnabled('testimonials')
      ? fetchAdminTestimonials('pending', 1)
          .then((r) => { pendingTestimonialCount.value = r.total })
          .catch(() => undefined)
      : Promise.resolve(),
    fetchReportsSummary()
      .then((r) => { summary.value = r })
      .catch(() => undefined),
    latestEvent.value
      ? fetchEventAccountingSummary(latestEvent.value.id)
          .then((r) => { eventSummary.value = r })
          .catch(() => undefined) // the latest-event card then shows just the event itself
      : Promise.resolve(),
  ])
})
</script>

<template>
  <div class="ds-scope dash-page">
    <div class="dash-top">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s dash-greeting">{{ greeting }}</h1>
      </div>
      <div class="dash-actions">
        <BaseButton to="/admin/events/new" size="sm">+ New event</BaseButton>
        <BaseButton to="/admin/newsletter/issues/new" variant="secondary" size="sm">Send newsletter</BaseButton>
        <BaseButton variant="secondary" size="sm" class="customise-button" @click="customiseOpen = true">Customise</BaseButton>
      </div>
    </div>

    <hr class="ds-section-line" />

    <GettingStartedCard />

    <!-- Needs your attention -->
    <section v-if="isShown('todo')" class="ds-card dash-todo">
      <h2 class="dash-card-title">Needs your attention</h2>
      <p v-if="summary && !attentionCount && !showCheckinRow" class="ds-meta dash-all-clear">Nothing needs your attention right now.</p>

      <div v-if="ticketsOn && pendingOrderCount" class="dash-task">
        <span class="dash-task-n dash-task-urgent">{{ pendingOrderCount }}</span>
        <div class="dash-task-text">
          <strong>{{ pendingOrderCount === 1 ? 'Order' : 'Orders' }} awaiting payment confirmation</strong>
          <small>{{ pendingCount }} pending · {{ pendingVerificationCount }} pending verification: cash and Vipps-QR need an admin to confirm</small>
        </div>
        <BaseButton to="/admin/orders?status=pending,pending_verification" variant="secondary" size="sm">Review orders</BaseButton>
      </div>

      <div v-if="membershipsOn && pendingMembershipCount" class="dash-task">
        <span class="dash-task-n dash-task-urgent">{{ pendingMembershipCount }}</span>
        <div class="dash-task-text">
          <strong>Membership request{{ pendingMembershipCount === 1 ? '' : 's' }} awaiting review</strong>
          <small>Approve or follow up</small>
        </div>
        <BaseButton to="/admin/members?status=pending" variant="secondary" size="sm">Review requests</BaseButton>
      </div>

      <div v-if="expiredMembers" class="dash-task">
        <span class="dash-task-n dash-task-warn">{{ expiredMembers }}</span>
        <div class="dash-task-text">
          <strong>{{ expiredMembers === 1 ? 'Membership' : 'Memberships' }} expired</strong>
          <small>Renew or send a reminder</small>
        </div>
        <BaseButton to="/admin/members?status=expired" variant="secondary" size="sm">View</BaseButton>
      </div>

      <div v-if="pendingTestimonialCount" class="dash-task">
        <span class="dash-task-n dash-task-warn">{{ pendingTestimonialCount }}</span>
        <div class="dash-task-text">
          <strong>Testimonial{{ pendingTestimonialCount === 1 ? '' : 's' }} awaiting review</strong>
          <small>Approve or reject before they show on the site</small>
        </div>
        <BaseButton to="/admin/testimonials?status=pending" variant="secondary" size="sm">Review testimonials</BaseButton>
      </div>

      <div v-if="showCheckinRow && latestEvent && eventSummary" class="dash-task dash-task-info">
        <span class="dash-task-n dash-task-muted">{{ eventSummary.tickets_checked_in }}</span>
        <div class="dash-task-text">
          <strong>Check-ins for {{ latestEvent.title }}</strong>
          <small>{{ eventSummary.tickets_checked_in }} of {{ eventSummary.tickets_expected }} tickets scanned{{ phase === 'expired' ? ': event has ended' : '' }}</small>
        </div>
        <BaseButton :to="`/admin/accounting/${latestEvent.id}`" variant="secondary" size="sm">Open accounting</BaseButton>
      </div>
    </section>

    <!-- Key numbers -->
    <section v-if="isShown('kpi')" class="dash-kpis">
      <router-link v-if="ticketsOn" to="/admin/payments" class="ds-card ds-card-interactive dash-kpi dash-kpi-hi">
        <p class="dash-small">Revenue</p>
        <div class="dash-kpi-value">{{ summary ? formatPriceRoundedGrouped(summary.revenue_total) : '—' }}</div>
        <p class="dash-note">Paid orders, all events</p>
      </router-link>
      <router-link v-if="ticketsOn" to="/admin/tickets" class="ds-card ds-card-interactive dash-kpi">
        <p class="dash-small">Tickets issued</p>
        <div class="dash-kpi-value">{{ summary ? summary.tickets_total : '—' }}</div>
        <p class="dash-note">Across {{ eventCount ?? '—' }} event{{ eventCount === 1 ? '' : 's' }}</p>
      </router-link>
      <router-link v-if="ticketsOn" to="/admin/orders" class="ds-card ds-card-interactive dash-kpi">
        <p class="dash-small">Paid orders</p>
        <div class="dash-kpi-value">{{ summary ? paidOrders : '—' }}</div>
        <p class="dash-note">of {{ totalOrders }} · {{ successRate }}% success</p>
      </router-link>
      <router-link v-if="membershipsOn" to="/admin/members" class="ds-card ds-card-interactive dash-kpi">
        <p class="dash-small">Active members</p>
        <div class="dash-kpi-value">{{ summary ? activeMembers : (memberCount ?? '—') }}</div>
        <p class="dash-note">{{ activeByType.length ? activeByType.map(([type, n]) => `${n} ${humanize(type).toLowerCase()}`).join(' · ') : `${memberCount ?? '—'} on the roster` }}</p>
      </router-link>
    </section>

    <div v-if="isShown('event') || isShown('orders')" class="dash-two" :class="{ 'dash-two-single': !(isShown('event') && isShown('orders')) }">
      <!-- Latest event -->
      <section v-if="eventsOn && isShown('event')" class="ds-card dash-event">
        <div class="dash-head">
          <h2 class="dash-card-title">Latest event</h2>
          <router-link v-if="latestEvent" :to="`/admin/accounting/${latestEvent.id}`" class="dash-link">Open accounting →</router-link>
        </div>
        <p v-if="!latestEvent" class="ds-meta">No events yet.</p>
        <template v-else>
          <h3 class="dash-event-title">
            {{ latestEvent.title }}
            <span v-if="phase" class="ds-badge" :class="EVENT_PHASE_BADGE[phase]">{{ EVENT_PHASE_LABEL[phase] }}</span>
          </h3>
          <div v-if="eventSummary" class="dash-ms">
            <div><small>Net revenue</small><b class="dash-net">{{ formatPriceRoundedGrouped(eventSummary.net_total) }}</b></div>
            <div><small>Tickets sold</small><b>{{ eventSummary.tickets_sold }}</b></div>
            <div><small>Coupon tickets</small><b>{{ couponTickets }}</b></div>
          </div>
          <template v-if="eventSummary">
            <div class="dash-lbl"><span>Check-in</span><span>{{ eventSummary.tickets_checked_in }} of {{ eventSummary.tickets_expected }}</span></div>
            <div class="dash-progress"><i :style="{ width: `${checkinRate}%` }"></i></div>
            <template v-if="couponGross > 0">
              <div class="dash-lbl"><span>Coupon discounts given</span><span>{{ formatPriceRoundedGrouped(couponDiscount) }} of {{ formatPriceRoundedGrouped(couponGross) }}</span></div>
              <div class="dash-progress"><i class="dash-progress-amber" :style="{ width: `${couponShare}%` }"></i></div>
            </template>
          </template>
        </template>
      </section>

      <!-- Orders by status -->
      <section v-if="ticketsOn && isShown('orders')" class="ds-card dash-orders">
        <div class="dash-head">
          <h2 class="dash-card-title">Orders by status</h2>
          <router-link to="/admin/orders" class="dash-link">All orders →</router-link>
        </div>
        <p v-if="summary && !orderSegments.length" class="ds-meta">No orders yet.</p>
        <template v-else-if="summary">
          <div class="dash-stack" role="img" aria-label="Orders by status">
            <i v-for="seg in orderSegments" :key="seg.status" :style="{ width: `${seg.width}%`, background: seg.colour }"></i>
          </div>
          <ul class="dash-legend">
            <li v-for="seg in orderSegments" :key="seg.status" :style="{ '--c': seg.colour }">
              <span>{{ orderStatusLabel(seg.status) }}</span>
              <b>{{ seg.count }}</b>
            </li>
          </ul>
        </template>
      </section>
    </div>

    <div v-if="isShown('recent') || isShown('members')" class="dash-two" :class="{ 'dash-two-single': !(isShown('recent') && isShown('members')) }">
      <!-- Latest orders -->
      <section v-if="ticketsOn && isShown('recent')" class="ds-card dash-recent">
        <div class="dash-head">
          <h2 class="dash-card-title">Latest orders</h2>
          <router-link to="/admin/orders" class="dash-link">View all →</router-link>
        </div>
        <p v-if="!recentOrders.length" class="ds-meta">No orders yet.</p>
        <div v-for="order in recentOrders" :key="order.id" class="dash-order-row">
          <div class="dash-order-main">
            <strong>{{ order.customer_name }}</strong>
            <small>{{ orderSubtitle(order) }}</small>
          </div>
          <b class="dash-order-amount">{{ formatPriceGrouped(order.total_amount) }}</b>
          <span class="ds-badge" :class="order.payment_status === 'paid' ? 'ds-badge-success' : order.payment_status === 'pending' || order.payment_status === 'pending_verification' ? 'ds-badge-accent' : 'ds-badge-neutral'">{{ orderStatusLabel(order.payment_status) }}</span>
        </div>
      </section>

      <!-- Membership -->
      <section v-if="membershipsOn && isShown('members')" class="ds-card dash-members">
        <div class="dash-head">
          <h2 class="dash-card-title">Membership</h2>
          <router-link to="/admin/members" class="dash-link">Members →</router-link>
        </div>
        <p v-if="summary && !activeMembers && !expiredMembers" class="ds-meta">No memberships yet.</p>
        <template v-else-if="summary">
          <div class="dash-big">{{ activeMembers }}</div>
          <p class="dash-note">active members</p>
          <ul class="dash-legend">
            <li v-for="[type, count] in activeByType" :key="type" style="--c: var(--ds-status-success)">
              <span>{{ humanize(type) }}</span>
              <b>{{ count }}</b>
            </li>
            <li v-if="expiredMembers" style="--c: var(--ds-status-warning)">
              <span>Expired</span>
              <b>{{ expiredMembers }}</b>
            </li>
          </ul>
        </template>
      </section>
    </div>

    <BaseModal v-model="customiseOpen" title="Customise dashboard">
      <p class="ds-meta">Show what you act on. Hide what rarely changes.</p>
      <ul class="dash-options">
        <li v-for="widget in WIDGETS" :key="widget.key">
          <label class="dash-option">
            <input type="checkbox" :checked="isShown(widget.key)" :data-widget="widget.key" @change="setShown(widget.key, ($event.target as HTMLInputElement).checked)" />
            <span><strong>{{ widget.title }}</strong><small>{{ widget.hint }}</small></span>
          </label>
        </li>
      </ul>
      <div class="dash-modal-actions"><BaseButton variant="ghost" @click="customiseOpen = false">Done</BaseButton></div>
    </BaseModal>
  </div>
</template>

<style scoped>
.dash-page { container-type: inline-size; max-width: 1120px; display: flex; flex-direction: column; gap: var(--ds-space-5); }
.dash-page :deep(.ds-card) { padding: 18px 20px; }
.dash-top { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap; }
.dash-greeting { font-size: clamp(24px, 2.8vw, 32px); }
.dash-actions { display: flex; gap: var(--ds-space-2); flex-wrap: wrap; }
.dash-card-title { margin: 0; font-size: 11px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ds-text-primary); font-family: var(--ds-font-body); }
.dash-head { display: flex; justify-content: space-between; align-items: center; gap: var(--ds-space-3); margin-bottom: var(--ds-space-3); }
.dash-link { font-size: 12px; font-weight: 600; text-decoration: none; color: var(--ds-text-primary); white-space: nowrap; }
.dash-small { margin: 0; font-size: 10.5px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ds-text-muted); white-space: nowrap; }
.dash-note { margin: 0; font-size: 11.5px; color: var(--ds-text-faint); }

/* Needs your attention */
.dash-todo { padding-top: 14px; padding-bottom: 6px; }
.dash-all-clear { margin: var(--ds-space-3) 0 var(--ds-space-2); }
.dash-task { display: flex; align-items: center; gap: var(--ds-space-4); padding: 12px 0; border-top: 1px solid var(--ds-border-hairline); }
.dash-card-title + .dash-task, .dash-card-title + .dash-all-clear { border-top: 0; margin-top: var(--ds-space-2); }
.dash-task-n { font-family: var(--ds-font-display); font-size: 28px; line-height: 1; min-width: 34px; color: var(--ds-text-heading); }
.dash-task-urgent { color: var(--ds-text-primary); }
.dash-task-warn { color: var(--ds-status-warning); }
.dash-task-muted { color: var(--ds-text-muted); }
.dash-task-text { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.dash-task-text strong { font-weight: 600; font-size: 14px; color: var(--ds-text-heading); }
.dash-task-text small { font-size: 12.5px; color: var(--ds-text-muted); }
@container (max-width: 560px) { .dash-task { flex-wrap: wrap; } }

/* Key numbers */
.dash-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--ds-space-3); }
@container (max-width: 760px) { .dash-kpis { grid-template-columns: 1fr 1fr; } }
.dash-kpi { padding: 14px 18px !important; display: flex !important; flex-direction: column; gap: 2px; }
.dash-kpi-hi.ds-card { background: var(--ds-paper-300); border-color: var(--ds-paper-300); }
html.dark .dash-kpi-hi.ds-card { background: var(--ds-palm-800); border-color: var(--ds-palm-800); }
.dash-kpi-hi .dash-kpi-value { color: var(--ds-status-success-ink); }
.dash-kpi-value { font-family: var(--ds-font-display); font-size: clamp(1.5rem, 2.4vw, 2rem); line-height: 1.2; color: var(--ds-text-heading); white-space: nowrap; }

/* Two-column rows */
.dash-two { display: grid; grid-template-columns: 1.4fr 1fr; gap: var(--ds-space-4); align-items: stretch; }
.dash-two > .ds-card { height: 100%; margin: 0; box-sizing: border-box; }
.dash-two-single { grid-template-columns: 1fr; }
@container (max-width: 760px) { .dash-two { grid-template-columns: 1fr; } }

/* Latest event */
.dash-event-title { margin: 0 0 var(--ds-space-3); font-family: var(--ds-font-display); font-weight: 400; font-size: 26px; color: var(--ds-text-heading); display: flex; align-items: center; gap: var(--ds-space-3); flex-wrap: wrap; }
.dash-ms { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--ds-space-3); margin-bottom: var(--ds-space-4); }
.dash-ms small { display: block; font-size: 12px; color: var(--ds-text-muted); }
.dash-ms b { font-family: var(--ds-font-display); font-weight: 400; font-size: 24px; color: var(--ds-text-heading); white-space: nowrap; }
.dash-net { color: var(--ds-status-success-ink) !important; }
.dash-lbl { display: flex; justify-content: space-between; font-size: 12px; color: var(--ds-text-muted); margin: var(--ds-space-3) 0 4px; }
.dash-progress { height: 8px; border-radius: 9px; background: var(--ds-border-hairline); overflow: hidden; }
.dash-progress i { display: block; height: 100%; background: var(--ds-status-success); }
.dash-progress .dash-progress-amber { background: var(--ds-status-warning); }

/* Orders by status + legends */
.dash-stack { display: flex; height: 12px; border-radius: 9px; overflow: hidden; gap: 2px; background: var(--ds-border-hairline); }
.dash-stack i { display: block; height: 100%; }
.dash-legend { list-style: none; margin: var(--ds-space-3) 0 0; padding: 0; }
.dash-legend li { display: flex; gap: var(--ds-space-2); align-items: center; padding: 4px 0; font-size: 13px; }
.dash-legend li::before { content: ''; width: 9px; height: 9px; border-radius: 50%; background: var(--c); flex: none; }
.dash-legend span { flex: 1; color: var(--ds-text-muted); }
.dash-legend b { font-weight: 600; color: var(--ds-text-heading); }

/* Latest orders */
.dash-order-row { display: flex; gap: var(--ds-space-3); align-items: center; padding: 10px 0; border-top: 1px solid var(--ds-border-hairline); }
.dash-head + .dash-order-row { border-top: 0; }
.dash-order-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.dash-order-main strong { font-weight: 500; font-size: 14px; color: var(--ds-text-heading); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dash-order-main small { font-size: 12px; color: var(--ds-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dash-order-amount { white-space: nowrap; font-size: 14px; color: var(--ds-text-heading); }

/* Membership */
.dash-big { font-family: var(--ds-font-display); font-size: 40px; line-height: 1; color: var(--ds-text-heading); }

/* Customise */
.dash-options { list-style: none; margin: var(--ds-space-3) 0 0; padding: 0; }
.dash-option { display: flex; gap: var(--ds-space-3); align-items: flex-start; padding: 10px 0; border-top: 1px solid var(--ds-border-hairline); cursor: pointer; }
.dash-option input { margin-top: 4px; width: 16px; height: 16px; accent-color: var(--ds-action-primary); }
.dash-option strong { display: block; font-weight: 500; }
.dash-option small { color: var(--ds-text-muted); font-size: 12px; }
.dash-modal-actions { margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; }
</style>
