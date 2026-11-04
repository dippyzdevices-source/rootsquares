<script setup lang="ts">
import VippsQrPicture from '../../components/ui/VippsQrPicture.vue'
import { moduleEnabled } from '../../services/modules'
import { ref, computed, onMounted } from 'vue'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import TicketQrCarousel, { type CarouselTicket } from './TicketQrCarousel.vue'
import {
  fetchMyMember,
  fetchMyMemberships,
  fetchMembershipTypes,
  requestMembershipRenewal,
  cancelMyMembershipRequest,
  fetchMyTaskAssignments,
  MemberNotFoundError,
  RenewalConflictError,
  type MemberProfile,
  type MembershipRecord,
  type MyTaskAssignment,
} from '../../services/memberApi'
import { fetchMyOrders, type Order } from '../../services/ordersApi'
import { formatEventDate } from '../../utils/date'
import { formatMembershipPrice } from '../../utils/membership'
import { humanize } from '../../utils/formatEnum'
import { useToast } from '../../composables/useToast'
import ChildMembershipPayments from '../../components/ChildMembershipPayments.vue'
import { useLookup } from '../../composables/useLookup'
import { useAuthStore } from '../../stores/auth'
import {
  fetchMyPeriods,
  type MembershipTypeChange,
  startPeriodPayment,
  refreshVippsPayment,
  type MembershipPeriod,
  type MyPeriodsResponse,
} from '../../services/membershipPaymentsApi'
import type { BankDetails } from '../../services/donationsApi'
import { formatPrice } from '../../utils/money'

const ticketsOn = moduleEnabled('tickets') // W8-R29
const volunteeringOn = moduleEnabled('volunteering') // W8-R20: the volunteering preview belongs to the Volunteering module
const membershipsOn = moduleEnabled('memberships') // W8-R19: the membership parts of the dashboard belong to the Memberships module
const { label: membershipStatusLabel } = useLookup('membership_status')
const toast = useToast()
const { label: taskCategoryLabel } = useLookup('task_category')
const auth = useAuthStore()

const loading = ref(true)
const errorMessage = ref('')
const profile = ref<MemberProfile | null>(null)
const memberships = ref<MembershipRecord[]>([])
const requestingRenewal = ref(false)
const renewalType = ref('')
const renewalTypeOptions = ref<{ value: string; label: string; detail: string }[]>([])
const periods = ref<MembershipPeriod[]>([])
const periodsError = ref(false)
// Status of the membership the periods belong to — "pending" means a request waiting for its first payment.
const periodsMembershipStatus = ref<string | null>(null)
const changingPlan = ref(false)
const cancelOpen = ref(false)
const cancelling = ref(false)
const selectedPeriodIds = ref<number[]>([])
const paying = ref(false)
const typeChanges = ref<MembershipTypeChange[]>([])
const vippsApp = ref<{ enabled: boolean; surcharge_percent: number }>({ enabled: false, surcharge_percent: 0 })
const stripeCard = ref<{ enabled: boolean; surcharge_percent: number }>({ enabled: false, surcharge_percent: 0 })
const cash = ref<{ enabled: boolean; note: string }>({ enabled: false, note: '' })
const vippsQr = ref<{ enabled: boolean; number: string | null; image_url?: string | null }>({ enabled: false, number: null })
const bank = ref<{ enabled: boolean; details: BankDetails | null }>({ enabled: false, details: null })
const payMethod = ref<'qr' | 'app' | 'card' | 'bank' | 'cash'>('qr')
const availableMethods = computed(() => (['qr', 'app', 'card', 'bank', 'cash'] as const).filter((m) => (m === 'qr' ? vippsQr.value.enabled : m === 'app' ? vippsApp.value.enabled : m === 'card' ? stripeCard.value.enabled : m === 'bank' ? bank.value.enabled : cash.value.enabled)))
const bankRows = computed(() => {
  const b = bank.value.details
  if (!b) return []
  return [
    { label: 'Account holder', value: b.holder },
    { label: 'Bank', value: b.bank_name },
    { label: 'Account number', value: b.account_number },
    { label: 'IBAN', value: b.iban },
    { label: 'BIC / SWIFT', value: b.bic },
  ].filter((row) => row.value)
})
const orders = ref<Order[]>([])
const taskAssignments = ref<MyTaskAssignment[]>([])

// The single soonest upcoming event this member is assigned to help with — mirrors
// "Next tickets" above: only ever the next one, not the full history (that's the
// dedicated Volunteering page).
const nextTaskAssignment = computed(() => {
  const upcoming = taskAssignments.value
    .filter((a) => new Date(a.event_end_datetime ?? a.event_start_datetime) >= new Date())
    .sort((a, b) => new Date(a.event_start_datetime).getTime() - new Date(b.event_start_datetime).getTime())
  return upcoming[0] ?? null
})

// The 2 soonest upcoming events this member holds *confirmed* tickets for — pending
// (unpaid/awaiting verification) and anything else non-paid is excluded, matching how
// "Next tickets" is meant to read as tickets that are actually good to use, not to-be-settled.
const upcomingTicketOrders = computed(() =>
  orders.value
    .filter(
      (order) =>
        order.payment_status === 'paid' &&
        order.event_start_datetime &&
        new Date(order.event_start_datetime) >= new Date(),
    )
    .sort((a, b) => new Date(a.event_start_datetime!).getTime() - new Date(b.event_start_datetime!).getTime())
    .slice(0, 2),
)

function ticketCount(order: Order): number {
  return order.items.reduce((sum, item) => sum + item.tickets.length, 0)
}

function carouselTickets(order: Order): CarouselTicket[] {
  return order.items.flatMap((item) =>
    item.tickets.map((ticket) => ({
      id: ticket.id,
      ticketTypeName: item.ticket_type_name,
      ticketCode: ticket.ticket_code,
      status: ticket.status,
      qrCodeDataUrl: ticket.qr_code_data_url,
    })),
  )
}

// Matches the reference design's "Next tickets" ticket row: weekday/day-number/month stacked as
// a compact date badge, plus the row's own start time.
function dateBadgeParts(iso: string): { dow: string; day: string; month: string; time: string } {
  const date = new Date(iso)
  return {
    dow: date.toLocaleDateString('en-GB', { weekday: 'short' }).toUpperCase(),
    day: date.toLocaleDateString('en-GB', { day: 'numeric' }),
    month: date.toLocaleDateString('en-GB', { month: 'short' }).toUpperCase(),
    time: date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
  }
}

const selectedOrder = ref<Order | null>(null)

function currentMembership(): MembershipRecord | null {
  const active = memberships.value.find((m) => m.status === 'active')
  return active ?? memberships.value[0] ?? null
}

function hasActiveMembership(): boolean {
  return memberships.value.some((m) => m.status === 'active')
}

function pendingRequest(): MembershipRecord | null {
  return memberships.value.find((m) => m.status === 'pending') ?? null
}

// A request that already has its periods: pay the one current period to activate it.
const awaitingFirstPayment = computed(() => periodsMembershipStatus.value === 'pending' && periods.value.length > 0)

function applyPeriods(res: MyPeriodsResponse) {
  periods.value = res.items
  typeChanges.value = res.type_changes ?? []
  vippsApp.value = res.vipps_app ?? vippsApp.value
  stripeCard.value = res.stripe ?? stripeCard.value
  cash.value = res.cash ?? cash.value
  bank.value = res.bank ?? bank.value
  vippsQr.value = res.vipps_qr ?? vippsQr.value
  // A method that is no longer on offer must not stay selected (Vipps QR is off until the square has its own number).
  if (!availableMethods.value.includes(payMethod.value) && availableMethods.value.length > 0) payMethod.value = availableMethods.value[0]
  periodsMembershipStatus.value = res.membership?.status ?? null
  if (res.membership?.status === 'pending') {
    // Preselect the single payable period so the payment options are open straight away.
    selectedPeriodIds.value = res.items.filter((p) => p.status === 'unpaid' && !p.payment_pending).map((p) => p.id)
  }
}

const unpaidPeriods = computed(() => periods.value.filter((p) => p.status === 'unpaid' && !p.payment_pending))
const awaitingPeriods = computed(() => periods.value.filter((p) => p.status === 'unpaid' && p.payment_pending))
const unpaidTotal = computed(() => unpaidPeriods.value.reduce((sum, p) => sum + p.amount, 0))

function selectedTotal(): number {
  return periods.value
    .filter((p) => selectedPeriodIds.value.includes(p.id))
    .reduce((sum, p) => sum + p.amount, 0)
}

const dueCount = computed(() => unpaidPeriods.value.length)
const allDueSelected = computed(
  () => unpaidPeriods.value.length > 0 && unpaidPeriods.value.every((p) => selectedPeriodIds.value.includes(p.id)),
)

function toggleAllDue() {
  selectedPeriodIds.value = allDueSelected.value ? [] : unpaidPeriods.value.map((p) => p.id)
}

function togglePeriod(id: number) {
  if (selectedPeriodIds.value.includes(id)) {
    selectedPeriodIds.value = selectedPeriodIds.value.filter((existing) => existing !== id)
  } else {
    selectedPeriodIds.value = [...selectedPeriodIds.value, id]
  }
}

async function reportVippsPayment() {
  paying.value = true
  try {
    await startPeriodPayment({ periodIds: selectedPeriodIds.value, provider: 'vipps_qr' })
    toast.success("Thanks — we've noted your payment and will confirm it shortly.")
    selectedPeriodIds.value = []
    applyPeriods(await fetchMyPeriods())
  } catch {
    toast.error('Could not report the payment')
  } finally {
    paying.value = false
  }
}

// Bank transfer: the member says they have transferred the money; an admin confirms once it has arrived.
async function reportBankPayment() {
  paying.value = true
  try {
    await startPeriodPayment({ periodIds: selectedPeriodIds.value, provider: 'bank_transfer' })
    toast.success('Thanks — an admin will confirm your payment once the money has arrived.')
    selectedPeriodIds.value = []
    applyPeriods(await fetchMyPeriods())
  } catch {
    toast.error('Could not register the bank transfer')
  } finally {
    paying.value = false
  }
}

// Cash: the member says they will pay in cash; an admin confirms once it is received.
async function reportCashPayment() {
  paying.value = true
  try {
    await startPeriodPayment({ periodIds: selectedPeriodIds.value, provider: 'cash' })
    toast.success("Thanks — an admin will confirm your payment once the cash is received.")
    selectedPeriodIds.value = []
    applyPeriods(await fetchMyPeriods())
  } catch {
    toast.error('Could not register the cash payment')
  } finally {
    paying.value = false
  }
}

// Display only — the backend computes the real fee (same round-half-up on øre) and charges that.
const appFee = computed(() => Math.floor((selectedTotal() * vippsApp.value.surcharge_percent + 50) / 100))

const cardFee = computed(() => Math.floor((selectedTotal() * stripeCard.value.surcharge_percent + 50) / 100))

async function payWithCard() {
  paying.value = true
  try {
    const res = await startPeriodPayment({ periodIds: selectedPeriodIds.value, provider: 'stripe' })
    if (!res.redirect_url) throw new Error('No redirect URL')
    window.location.href = res.redirect_url
  } catch {
    toast.error('Could not start the card payment')
    paying.value = false
  }
}

async function payWithVippsApp() {
  paying.value = true
  try {
    const res = await startPeriodPayment({ periodIds: selectedPeriodIds.value, provider: 'vipps_app' })
    if (!res.redirect_url) throw new Error('No redirect URL')
    window.location.href = res.redirect_url
  } catch {
    toast.error('Could not start the Vipps payment')
    paying.value = false
  }
}

// Back from Vipps (?vipps_payment=<id>): ask the backend to check the real payment state.
async function checkReturnFromVipps() {
  const params = new URLSearchParams(window.location.search)
  const id = Number(params.get('vipps_payment'))
  if (!id) return
  window.history.replaceState({}, '', window.location.pathname)
  try {
    const { status } = await refreshVippsPayment(id)
    if (status === 'paid') toast.success('Payment received — thank you!')
    else if (status === 'initiated') toast.info("We're still waiting for the payment to be confirmed.")
    else toast.error('The payment was not completed.')
    applyPeriods(await fetchMyPeriods())
    if (status === 'paid') memberships.value = await fetchMyMemberships() // a first payment activates the membership
  } catch {
    toast.error('Could not check your payment. Please refresh the page.')
  }
}

function membershipBadgeTone(status: string): string {
  if (status === 'active') return 'ds-badge-success'
  if (status === 'expired' || status === 'cancelled' || status === 'suspended') return 'ds-badge-danger'
  return 'ds-badge-neutral'
}

async function cancelRequest() {
  cancelling.value = true
  try {
    await cancelMyMembershipRequest()
    memberships.value = memberships.value.filter((m) => m.status !== 'pending')
    selectedPeriodIds.value = []
    changingPlan.value = false
    cancelOpen.value = false
    applyPeriods(await fetchMyPeriods())
    toast.success('Your membership request was cancelled')
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Could not cancel your request')
    cancelOpen.value = false
  } finally {
    cancelling.value = false
  }
}

async function requestRenewal() {
  requestingRenewal.value = true
  try {
    const membership = await requestMembershipRenewal(renewalType.value)
    // A new request replaces an unpaid pending one.
    memberships.value = [membership, ...memberships.value.filter((m) => m.status !== 'pending')]
    changingPlan.value = false
    try {
      applyPeriods(await fetchMyPeriods())
    } catch {
      periodsError.value = true
    }
    toast.success(
      awaitingFirstPayment.value
        ? 'Request saved — complete the payment below to activate your membership.'
        : 'Your membership request was submitted',
    )
  } catch (err) {
    if (err instanceof RenewalConflictError) {
      toast.error(err.message)
    } else {
      toast.error('Could not submit your membership request')
    }
  } finally {
    requestingRenewal.value = false
  }
}

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    profile.value = await fetchMyMember()
  } catch (err) {
    if (err instanceof MemberNotFoundError) {
      profile.value = null
    } else {
      errorMessage.value = 'Could not load your profile.'
    }
  }

  try {
    if (!membershipsOn) throw new Error('no Memberships module')
    memberships.value = await fetchMyMemberships()
  } catch {
    // Membership status is secondary — profile errors already surfaced above.
  }

  try {
    if (!membershipsOn) throw new Error('no Memberships module')
    const types = await fetchMembershipTypes()
    renewalTypeOptions.value = types.map((t) => ({
      value: t.name,
      label: humanize(t.name),
      detail: formatMembershipPrice(t),
    }))
    renewalType.value = types[0]?.name ?? ''
  } catch {
    // Renewal form is secondary — profile/membership errors already surfaced above.
  }

  try {
    if (!membershipsOn) throw new Error('no Memberships module')
    applyPeriods(await fetchMyPeriods())
  } catch {
    periodsError.value = membershipsOn
  }

  try {
    if (!ticketsOn) throw new Error('no Tickets module')
    orders.value = (await fetchMyOrders()).items
  } catch {
    // Ticket preview is secondary — profile/membership errors already surfaced above.
  }

  try {
    if (!volunteeringOn) throw new Error('no Volunteering module')
    taskAssignments.value = await fetchMyTaskAssignments()
  } catch {
    // Volunteering preview is secondary — profile/membership errors already surfaced above.
  }

  loading.value = false
  void checkReturnFromVipps()
}

onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="max-width: 780px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <BaseLoadingState v-if="loading" label="Loading your dashboard…" />
      <div v-else-if="errorMessage" class="ds-alert ds-alert-danger"><div>{{ errorMessage }}</div></div>

      <template v-else>
        <div class="ds-card" style="display: flex; align-items: center; gap: var(--ds-space-5); flex-wrap: wrap">
          <BaseAvatar :src="profile?.photo_url ?? auth.avatarUrl" :name="auth.displayName ?? profile?.name" size="xl" />
          <div style="flex: 1; min-width: 200px">
            <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Good to see you</p>
            <h1 class="ds-title" style="margin-top: 2px">{{ profile?.name ?? auth.displayName ?? 'Welcome' }}</h1>
            <p v-if="auth.user?.email" class="ds-meta" style="margin-top: 4px">{{ auth.user.email }}</p>
            <p v-if="profile?.phone" class="ds-meta" style="margin-top: 2px">{{ profile.phone }}</p>
          </div>
          <span v-if="membershipsOn && hasActiveMembership()" class="ds-badge ds-badge-success">Membership active</span>
        </div>

        <div v-if="!profile" class="ds-alert ds-alert-info">
          <div>
            You don't have a profile yet.
            <router-link to="/member/settings" style="font-weight: 600">Add your contact details</router-link>
            to get started.
          </div>
        </div>

        <div v-if="membershipsOn" class="ds-cards ds-cards--3">
          <div class="ds-card">
            <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Membership</p>
            <div style="font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); line-height: 1.05; color: var(--ds-text-heading); margin-top: 4px">
              {{ currentMembership() ? humanize(currentMembership()!.membership_type) : 'None yet' }}
            </div>
            <p class="ds-caption" style="margin-top: 4px">{{ currentMembership() ? membershipStatusLabel(currentMembership()!.status) : 'Request one below' }}</p>
          </div>
          <div class="ds-card">
            <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow); color: var(--ds-text-primary)">Household</p>
            <div style="font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); line-height: 1.05; color: var(--ds-text-primary); margin-top: 4px">
              {{ (profile?.family_members?.length ?? 0) + (profile ? 1 : 0) }}
            </div>
            <p class="ds-caption" style="margin-top: 4px">
              <router-link to="/member/family" style="color: var(--ds-text-primary); font-weight: 600">Manage family →</router-link>
            </p>
          </div>
          <div class="ds-card">
            <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Dues</p>
            <div style="font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); line-height: 1.05; color: var(--ds-text-heading); margin-top: 4px">
              {{ unpaidPeriods.length ? formatPrice(unpaidTotal) : 'None' }}
            </div>
            <p class="ds-caption" style="margin-top: 4px">{{ unpaidPeriods.length ? `${unpaidPeriods.length} period(s) unpaid` : 'All paid up' }}</p>
          </div>
        </div>

        <section v-if="ticketsOn" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div style="display: flex; align-items: baseline; justify-content: space-between">
            <h2 class="ds-title">Next tickets</h2>
            <router-link to="/member/tickets" class="ds-eyebrow">All tickets</router-link>
          </div>
          <BaseEmptyState
            v-if="upcomingTicketOrders.length === 0"
            title="No upcoming tickets"
            description="Tickets for events you're attending soon will show up here."
          />
          <div v-else style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
            <div v-for="order in upcomingTicketOrders" :key="order.id" class="ds-ticket-row">
              <div class="ds-ticket-row-date">
                <span class="ds-ticket-row-dow">{{ dateBadgeParts(order.event_start_datetime!).dow }}</span>
                <span class="ds-ticket-row-day">{{ dateBadgeParts(order.event_start_datetime!).day }}</span>
                <span class="ds-ticket-row-month">{{ dateBadgeParts(order.event_start_datetime!).month }}</span>
              </div>
              <div class="ds-ticket-row-body">
                <p class="ds-body" style="font-family: var(--ds-font-display); font-size: var(--ds-text-subtitle)">{{ order.event_title ?? order.order_number }}</p>
                <p class="ds-caption" style="margin-top: 2px">
                  {{ dateBadgeParts(order.event_start_datetime!).time }} · {{ ticketCount(order) }} seat(s) · {{ order.order_number }}
                </p>
              </div>
              <div class="ds-ticket-row-actions">
                <span class="ds-badge ds-badge-success">Confirmed</span>
                <BaseButton type="button" variant="secondary" size="sm" @click="selectedOrder = order">
                  Show
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="5" height="5" x="3" y="3" rx="1" /><rect width="5" height="5" x="16" y="3" rx="1" /><rect width="5" height="5" x="3" y="16" rx="1" /><path d="M21 16h-3a2 2 0 0 0-2 2v3" /><path d="M21 21v.01" /><path d="M12 7v3a2 2 0 0 1-2 2H7" /><path d="M3 12h.01" /><path d="M12 3h.01" /><path d="M12 16v.01" /><path d="M16 12h1" /><path d="M21 12v.01" /><path d="M12 21v-1" /></svg>
                </BaseButton>
              </div>
            </div>
          </div>
        </section>

        <BaseModal
          :model-value="selectedOrder !== null"
          title="Your tickets"
          @update:model-value="(open) => { if (!open) selectedOrder = null }"
        >
          <TicketQrCarousel v-if="selectedOrder" :tickets="carouselTickets(selectedOrder)" />
        </BaseModal>

        <section v-if="volunteeringOn" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div style="display: flex; align-items: baseline; justify-content: space-between">
            <h2 class="ds-title">Next volunteering</h2>
            <router-link to="/member/volunteering" class="ds-eyebrow">All volunteering</router-link>
          </div>
          <BaseEmptyState
            v-if="!nextTaskAssignment"
            title="No upcoming volunteering"
            description="Tasks an admin assigns you to help with will show up here."
          />
          <div v-else class="ds-ticket-row">
            <div class="ds-ticket-row-date">
              <span class="ds-ticket-row-dow">{{ dateBadgeParts(nextTaskAssignment.event_start_datetime).dow }}</span>
              <span class="ds-ticket-row-day">{{ dateBadgeParts(nextTaskAssignment.event_start_datetime).day }}</span>
              <span class="ds-ticket-row-month">{{ dateBadgeParts(nextTaskAssignment.event_start_datetime).month }}</span>
            </div>
            <div class="ds-ticket-row-body">
              <p class="ds-body" style="font-family: var(--ds-font-display); font-size: var(--ds-text-subtitle)">{{ nextTaskAssignment.event_title }}</p>
              <p class="ds-caption" style="margin-top: 2px">{{ dateBadgeParts(nextTaskAssignment.event_start_datetime).time }}</p>
            </div>
            <div class="ds-ticket-row-actions">
              <span class="ds-badge ds-badge-accent">{{ taskCategoryLabel(nextTaskAssignment.category) }}</span>
            </div>
          </div>
        </section>

        <ChildMembershipPayments v-if="membershipsOn" />

        <section v-if="membershipsOn" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <h2 class="ds-title">Membership Status</h2>
          <div class="ms-card">
            <header v-if="currentMembership()" class="ms-head">
              <div style="display: grid; gap: 4px">
                <h3 class="ms-title">{{ humanize(currentMembership()!.membership_type) }} membership</h3>
                <span class="ds-meta">Member since {{ formatEventDate(currentMembership()!.start_date) }}</span>
              </div>
              <span
                class="ms-pill"
                :class="
                  currentMembership()!.status === 'active'
                    ? (dueCount ? 'ms-pill-due' : 'ms-pill-ok')
                    : membershipBadgeTone(currentMembership()!.status) === 'ds-badge-danger'
                      ? 'ms-pill-bad'
                      : 'ms-pill-muted'
                "
              >
                <span class="ms-pill-dot"></span>
                <template v-if="currentMembership()!.status === 'active'">
                  {{ dueCount ? `Active · ${dueCount} due` : 'Active · all paid' }}
                </template>
                <template v-else>{{ membershipStatusLabel(currentMembership()!.status) }}</template>
              </span>
            </header>
            <BaseEmptyState
              v-else
              title="No membership yet"
              description="Request a membership below to get started."
            />

            <template v-if="pendingRequest()">
              <div v-if="awaitingFirstPayment" class="ds-alert ds-alert-warning pay-to-activate">
                <div v-if="awaitingPeriods.length > 0">
                  <strong class="ds-alert-title">Payment reported</strong>
                  We'll confirm it shortly — your {{ humanize(pendingRequest()!.membership_type) }} membership activates as soon as we do.
                </div>
                <div v-else>
                  <strong class="ds-alert-title">One more step to activate your membership</strong>
                  Pay {{ periods[0]?.label }} ({{ formatPrice(periods[0]?.amount ?? 0) }}) below — your
                  {{ humanize(pendingRequest()!.membership_type) }} membership starts as soon as the payment is confirmed.
                </div>
              </div>
              <div v-else class="ds-alert ds-alert-info">
                <div>
                  Membership request pending — {{ humanize(pendingRequest()!.membership_type) }}, awaiting
                  admin approval.
                </div>
              </div>
              <button
                v-if="awaitingFirstPayment && awaitingPeriods.length === 0 && !changingPlan"
                type="button"
                class="ms-linkbtn change-plan"
                @click="changingPlan = true"
              >
                Choose a different membership
              </button>
              <button
                v-if="awaitingFirstPayment && awaitingPeriods.length === 0"
                type="button"
                class="ms-linkbtn cancel-request"
                @click="cancelOpen = true"
              >
                Cancel request
              </button>
            </template>
            <div v-else-if="hasActiveMembership()" class="ds-alert ds-alert-success">
              <div>You already have an active {{ humanize(currentMembership()!.membership_type) }} membership.</div>
            </div>
            <div v-if="!hasActiveMembership() && (!pendingRequest() || changingPlan)" class="ms-plans-block">
              <div style="display: grid; gap: 6px">
                <p class="ms-eyebrow ms-eyebrow-primary">Join the community</p>
                <p class="ds-meta">Choose a membership. We'll confirm your request by email.</p>
              </div>
              <div class="ms-plans" role="radiogroup" aria-label="Membership type">
                <label
                  v-for="option in renewalTypeOptions"
                  :key="option.value"
                  class="ms-choice"
                  :class="{ 'ms-choice-on': renewalType === option.value }"
                >
                  <input v-model="renewalType" type="radio" name="ms-plan" :value="option.value" class="ms-sr" />
                  <span class="ms-radio" aria-hidden="true"><span v-if="renewalType === option.value" class="ms-radio-dot"></span></span>
                  <span class="ms-choice-title">{{ option.label }}</span>
                  <span class="ms-choice-aside">{{ option.detail }}</span>
                </label>
              </div>
              <div style="max-width: 280px">
                <BaseButton
                  type="button"
                  class="request-renewal"
                  :disabled="requestingRenewal || !renewalType"
                  style="width: 100%"
                  @click="requestRenewal"
                >
                  {{ requestingRenewal ? 'Requesting…' : changingPlan ? 'Switch membership' : 'Request membership' }}
                </BaseButton>
                <button v-if="changingPlan" type="button" class="ms-linkbtn keep-plan" style="margin-top: var(--ds-space-3)" @click="changingPlan = false">
                  Keep my current choice
                </button>
              </div>
            </div>

            <div v-if="periodsError" class="ds-alert ds-alert-danger">
              <div>Couldn't load your unpaid periods. Please try again shortly.</div>
            </div>
            <div v-else-if="periods.length > 0" class="ms-body">
              <div class="unpaid-block ms-col">
                <div style="display: flex; justify-content: space-between; align-items: baseline; gap: 12px">
                  <p class="ms-eyebrow">Choose periods to pay</p>
                  <button v-if="unpaidPeriods.length > 0" type="button" class="ms-linkbtn" @click="toggleAllDue">
                    {{ allDueSelected ? 'Clear' : 'Select all due' }}
                  </button>
                </div>
                <div class="ms-tiles">
                  <button
                    v-for="period in periods"
                    :key="period.id"
                    type="button"
                    class="ms-tile"
                    :class="{
                      'ms-tile-on': selectedPeriodIds.includes(period.id),
                      'ms-tile-paid': period.status === 'paid',
                      'ms-tile-wait': period.status === 'unpaid' && period.payment_pending,
                    }"
                    :disabled="period.status === 'paid' || period.payment_pending"
                    :aria-pressed="selectedPeriodIds.includes(period.id)"
                    :title="period.status === 'paid' ? 'Paid' : `${period.label} — ${formatPrice(period.amount)}`"
                    @click="togglePeriod(period.id)"
                  >
                    <span class="ms-tile-label">{{ period.label }}</span>
                    <span class="ms-tile-sub">
                      <template v-if="period.status === 'paid'">✓ Paid</template>
                      <template v-else-if="period.payment_pending">Awaiting</template>
                      <template v-else>{{ formatPrice(period.amount) }}</template>
                    </span>
                  </button>
                </div>
              </div>
              <aside v-if="unpaidPeriods.length > 0" class="payment-method-block ms-aside">
                <p class="ms-eyebrow">Payment</p>
                <div style="display: flex; justify-content: space-between; align-items: baseline; gap: 12px">
                  <span class="ds-meta">
                    {{ selectedPeriodIds.length ? `${selectedPeriodIds.length} period${selectedPeriodIds.length > 1 ? 's' : ''} selected` : 'No periods selected' }}
                  </span>
                  <span class="ms-total">{{ formatPrice(selectedTotal()) }}</span>
                </div>
                <p v-if="selectedPeriodIds.length === 0" class="ds-meta">Select the periods you want to pay.</p>
                <div v-if="selectedPeriodIds.length > 0 && availableMethods.length > 1" class="ms-methods" role="radiogroup" aria-label="Payment method">
                  <label v-if="vippsQr.enabled" class="ms-choice" :class="{ 'ms-choice-on': payMethod === 'qr' }">
                    <input v-model="payMethod" type="radio" name="ms-pay" value="qr" class="ms-sr" />
                    <span class="ms-radio" aria-hidden="true"><span v-if="payMethod === 'qr'" class="ms-radio-dot"></span></span>
                    <span><span class="ms-choice-title">Vipps</span><span class="ds-meta" style="display: block">Send to our Vipps number</span></span>
                    <span class="ms-choice-aside"></span>
                  </label>
                  <label v-if="vippsApp.enabled" class="ms-choice" :class="{ 'ms-choice-on': payMethod === 'app' }">
                    <input v-model="payMethod" type="radio" name="ms-pay" value="app" class="ms-sr" />
                    <span class="ms-radio" aria-hidden="true"><span v-if="payMethod === 'app'" class="ms-radio-dot"></span></span>
                    <span><span class="ms-choice-title">Vipps-App</span><span class="ds-meta" style="display: block">Pay directly in the Vipps App<br />(Convenience fee +{{ vippsApp.surcharge_percent }}%)</span></span>
                    <span class="ms-choice-aside"></span>
                  </label>
                  <label v-if="stripeCard.enabled" class="ms-choice" :class="{ 'ms-choice-on': payMethod === 'card' }">
                    <input v-model="payMethod" type="radio" name="ms-pay" value="card" class="ms-sr" />
                    <span class="ms-radio" aria-hidden="true"><span v-if="payMethod === 'card'" class="ms-radio-dot"></span></span>
                    <span><span class="ms-choice-title">Card</span><span class="ds-meta" style="display: block">Pay by card on a secure page<template v-if="stripeCard.surcharge_percent"><br />(Convenience fee +{{ stripeCard.surcharge_percent }}%)</template></span></span>
                    <span class="ms-choice-aside"></span>
                  </label>
                  <label v-if="bank.enabled" class="ms-choice" :class="{ 'ms-choice-on': payMethod === 'bank' }">
                    <input v-model="payMethod" type="radio" name="ms-pay" value="bank" class="ms-sr" />
                    <span class="ms-radio" aria-hidden="true"><span v-if="payMethod === 'bank'" class="ms-radio-dot"></span></span>
                    <span><span class="ms-choice-title">Bank transfer</span><span class="ds-meta" style="display: block">Transfer the money; an admin confirms it</span></span>
                    <span class="ms-choice-aside"></span>
                  </label>
                  <label v-if="cash.enabled" class="ms-choice" :class="{ 'ms-choice-on': payMethod === 'cash' }">
                    <input v-model="payMethod" type="radio" name="ms-pay" value="cash" class="ms-sr" />
                    <span class="ms-radio" aria-hidden="true"><span v-if="payMethod === 'cash'" class="ms-radio-dot"></span></span>
                    <span><span class="ms-choice-title">Cash</span><span class="ds-meta" style="display: block">Pay in person; an admin confirms it</span></span>
                    <span class="ms-choice-aside"></span>
                  </label>
                </div>
                <div v-if="selectedPeriodIds.length > 0 && vippsApp.enabled && payMethod === 'app'" class="vipps-app-panel" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
                  <div class="ms-breakdown">
                    <span>Selected</span><span>{{ formatPrice(selectedTotal()) }}</span>
                    <span>Convenience fee</span><span>{{ formatPrice(appFee) }}</span>
                    <strong>Total</strong><strong>{{ formatPrice(selectedTotal() + appFee) }}</strong>
                  </div>
                  <BaseButton type="button" :disabled="paying" style="width: 100%" @click="payWithVippsApp">
                    {{ paying ? 'Opening Vipps…' : `Pay ${formatPrice(selectedTotal() + appFee)} with Vipps` }}
                  </BaseButton>
                </div>
                <div v-else-if="selectedPeriodIds.length > 0 && stripeCard.enabled && payMethod === 'card'" class="card-panel" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
                  <div class="ms-breakdown">
                    <span>Selected</span><span>{{ formatPrice(selectedTotal()) }}</span>
                    <span v-if="cardFee > 0">Convenience fee</span><span v-if="cardFee > 0">{{ formatPrice(cardFee) }}</span>
                    <strong>Total</strong><strong>{{ formatPrice(selectedTotal() + cardFee) }}</strong>
                  </div>
                  <BaseButton type="button" :disabled="paying" style="width: 100%" @click="payWithCard">
                    {{ paying ? 'Opening the card page…' : `Pay ${formatPrice(selectedTotal() + cardFee)} by card` }}
                  </BaseButton>
                </div>
                <div v-else-if="selectedPeriodIds.length > 0 && bank.enabled && payMethod === 'bank'" class="bank-panel" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
                  <p class="ds-body" style="font-weight: 600">Bank transfer</p>
                  <dl class="bank-details" style="display: grid; grid-template-columns: max-content 1fr; gap: var(--ds-space-1) var(--ds-space-4); margin: 0">
                    <template v-for="row in bankRows" :key="row.label"><dt class="ds-meta">{{ row.label }}</dt><dd style="margin: 0">{{ row.value }}</dd></template>
                  </dl>
                  <p class="ds-meta">
                    Transfer {{ formatPrice(selectedTotal()) }} and write your full name as the message. Then tap the button below — we'll confirm your payment when the money has arrived.
                  </p>
                  <p v-if="bank.details?.note" class="ds-meta" style="white-space: pre-line">{{ bank.details.note }}</p>
                  <BaseButton type="button" class="bank-reported" :disabled="paying" style="width: 100%" @click="reportBankPayment">
                    {{ paying ? 'Reporting…' : "I've made this payment" }}
                  </BaseButton>
                </div>
                <div v-else-if="selectedPeriodIds.length > 0 && cash.enabled && payMethod === 'cash'" class="cash-panel" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
                  <p class="ds-body" style="font-weight: 600">Cash</p>
                  <p class="ds-meta cash-note" style="white-space: pre-line">{{ cash.note || 'Pay the amount in cash to the association. Your membership is confirmed once an admin has received it.' }}</p>
                  <BaseButton type="button" :disabled="paying" style="width: 100%" @click="reportCashPayment">
                    {{ paying ? 'Sending…' : `I'll pay ${formatPrice(selectedTotal())} in cash` }}
                  </BaseButton>
                </div>
                <div v-else-if="selectedPeriodIds.length > 0 && vippsQr.enabled && payMethod === 'qr'" class="vipps-panel" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
                  <p class="ds-body" style="font-weight: 600">Vipps</p>
                  <p v-if="vippsQr.number" class="ds-body" style="text-align: center">Vipps to <strong>{{ vippsQr.number }}</strong></p>
                  <div style="display: flex; justify-content: center"><VippsQrPicture :src="vippsQr.image_url" /></div>
                  <p class="ds-meta">
                    Pay {{ formatPrice(selectedTotal()) }} and mention your name in the payment message. Then tap the button below —
                    we'll confirm your payment as soon as possible.
                  </p>
                  <BaseButton type="button" :disabled="paying" style="width: 100%" @click="reportVippsPayment">
                    {{ paying ? 'Reporting…' : "I've made this payment" }}
                  </BaseButton>
                </div>
                <p v-else-if="selectedPeriodIds.length > 0 && availableMethods.length === 0" class="ds-meta no-payment-method">No payment method is set up yet. Please contact us to pay.</p>
              </aside>
            </div>
            <div v-if="awaitingPeriods.length > 0" class="ds-alert ds-alert-info awaiting-confirmation">
              <div>Payment reported for {{ awaitingPeriods.map((p) => p.label).join(', ') }} — awaiting confirmation.</div>
            </div>
            <p
              v-for="change in typeChanges"
              :key="change.changed_at"
              class="ds-caption type-change-note"
            >
              Membership changed from {{ change.from_type }} to {{ change.to_type }} on {{ formatEventDate(change.changed_at) }}.
            </p>
          </div>
        </section>
      </template>
    </div>

    <BaseModal v-model="cancelOpen" title="Cancel your membership request?">
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-body">You haven't paid anything yet, so nothing is lost. You can request a membership again any time.</p>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" size="md" @click="cancelOpen = false">Keep my request</BaseButton>
          <BaseButton type="button" variant="primary" size="md" class="confirm-cancel-request" :disabled="cancelling" @click="cancelRequest">
            {{ cancelling ? 'Cancelling…' : 'Cancel request' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </div>
</template>

<style scoped>
/* Membership status — design system "Membership status" (month/period tiles + payment summary + plan choice cards). */
.ms-card { display: grid; gap: var(--ds-space-5); background: var(--ds-surface-card); border: 1px solid var(--ds-border-hairline); border-radius: var(--ds-radius-lg); box-shadow: var(--ds-shadow-sm); padding: clamp(20px, 3vw, 32px); }
.ms-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.ms-title { font-family: var(--ds-font-display); font-size: var(--ds-text-title); color: var(--ds-text-heading); font-weight: 400; margin: 0; }
.ms-eyebrow { font: var(--ds-type-eyebrow); letter-spacing: var(--ds-tracking-eyebrow); text-transform: uppercase; color: var(--ds-text-muted); margin: 0; }
.ms-eyebrow-primary { color: var(--ds-text-primary); }
.ms-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; font-size: var(--ds-text-caption); font-weight: 600; }
.ms-pill-dot { width: 7px; height: 7px; border-radius: 999px; background: currentColor; }
.ms-pill-due { background: var(--ds-surface-accent-soft); color: var(--ds-status-accent-ink); }
.ms-pill-ok { background: var(--ds-palm-100); color: var(--ds-palm-700); }
.ms-pill-bad { background: var(--ds-surface-sunken); color: var(--ds-text-heading); }
.ms-pill-muted { background: var(--ds-surface-sunken); color: var(--ds-text-muted); }
.ms-body { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); gap: 28px; align-items: start; border-top: 1px solid var(--ds-border-hairline); padding-top: var(--ds-space-5); }
.ms-col { display: grid; gap: 14px; }
.ms-linkbtn { background: none; border: 0; padding: 0; cursor: pointer; color: var(--ds-text-primary); font-size: var(--ds-text-body-s); font-weight: 600; }
.ms-tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: 8px; }
.ms-tile { display: grid; gap: 2px; justify-items: start; padding: 10px 12px; border-radius: var(--ds-radius-md); cursor: pointer; text-align: left; background: var(--ds-surface-card); border: 1px solid var(--ds-border-default); color: var(--ds-text-heading); transition: all 0.15s; }
.ms-tile-label { font-weight: 600; font-size: var(--ds-text-body-s); }
.ms-tile-sub { font-size: var(--ds-text-caption); }
.ms-tile-paid, .ms-tile-wait { background: var(--ds-surface-sunken); border-color: transparent; color: var(--ds-text-muted); cursor: default; }
.ms-tile-on { background: var(--ds-action-primary); border-color: var(--ds-action-primary); color: var(--ds-text-on-primary); }
.ms-aside { display: grid; gap: 16px; padding: 20px; border-radius: var(--ds-radius-md); background: var(--ds-surface-page); border: 1px solid var(--ds-border-hairline); }
.ms-total { font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); color: var(--ds-text-heading); line-height: 1; }
.ms-plans-block { display: grid; gap: var(--ds-space-4); }
.ms-plans { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.ms-choice { position: relative; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 14px 16px; border-radius: var(--ds-radius-md); cursor: pointer; background: var(--ds-surface-card); border: 1px solid var(--ds-border-default); transition: all 0.15s; }
.ms-choice-on { background: var(--ds-surface-accent-soft); border-color: var(--ds-border-primary); box-shadow: 0 0 0 1px var(--ds-border-primary); }
.ms-choice-title { font-weight: 600; color: var(--ds-text-heading); }
.ms-choice-aside { font-size: var(--ds-text-body-s); color: var(--ds-text-body); white-space: nowrap; }
.ms-radio { width: 18px; height: 18px; border-radius: 999px; border: 1.5px solid var(--ds-border-strong); display: grid; place-items: center; }
.ms-choice-on .ms-radio { border-color: var(--ds-action-primary); }
.ms-radio-dot { width: 9px; height: 9px; border-radius: 999px; background: var(--ds-action-primary); }
.ms-methods { display: grid; gap: 8px; }
.ms-breakdown { display: grid; grid-template-columns: 1fr auto; gap: 4px 12px; font-size: var(--ds-text-body-s); color: var(--ds-text-body); }
.ms-breakdown strong { color: var(--ds-text-heading); }
.ms-sr { position: absolute; top: 0; left: 0; width: 1px; height: 1px; margin: 0; padding: 0; border: 0; overflow: hidden; clip: rect(0 0 0 0); clip-path: inset(50%); opacity: 0; pointer-events: none; }
</style>
