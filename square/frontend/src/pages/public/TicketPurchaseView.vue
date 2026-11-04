<script setup lang="ts">
import { moduleEnabled } from '../../services/modules'
import { isValidPhone, phoneMessage, phonePrefix } from '../../utils/phone'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseBreadcrumbs from '../../components/ui/BaseBreadcrumbs.vue'
import TicketAgeIcon from '../../components/ui/TicketAgeIcon.vue'
import VippsPaymentPanel from '../../components/ui/VippsPaymentPanel.vue'
import CashPaymentPanel from '../../components/ui/CashPaymentPanel.vue'
import BankPaymentPanel from '../../components/ui/BankPaymentPanel.vue'
import { fetchEvent, type EventDetail } from '../../services/eventsApi'
import { fetchTicketTypes, type TicketTypeSummary } from '../../services/ticketsApi'
import { checkout, confirmPayment, ValidationError, type Order } from '../../services/ordersApi'
import { fetchStripeConfig, fetchVippsAppConfig, vippsAppFee, type VippsAppConfig } from '../../services/vippsAppApi'
import { validateCoupon } from '../../services/couponsApi'
import { formatPrice } from '../../utils/money'
import { formatDateTime } from '../../utils/date'
import { groupTicketsByDay } from '../../utils/ticketDays'
import { useLookup } from '../../composables/useLookup'

const { label: paymentStatusLabel } = useLookup('payment_status')
const route = useRoute()

const event = ref<EventDetail | null>(null)
const ticketTypes = ref<TicketTypeSummary[]>([])
const quantities = ref<Record<number, number>>({})
const loading = ref(true)
const errors = ref<Record<string, string>>({})
const submitting = ref(false)
const confirmedOrder = ref<Order | null>(null)
const reportingPayment = ref(false)
const vippsApp = ref<VippsAppConfig>({ enabled: false, surcharge_percent: 0 })
const stripeCard = ref<VippsAppConfig>({ enabled: false, surcharge_percent: 0 })
const payMethod = ref<'qr' | 'app' | 'bank' | 'cash' | 'card'>('qr')

const form = ref({ customer_name: '', customer_email: '', customer_phone: phonePrefix() })

const couponsOn = moduleEnabled('coupons') // W8-R21: no coupon box without the Coupons module
const couponInput = ref('')
const appliedCoupon = ref<{
  code: string
  discount_percent: number
  allowedTicketTypeIds: number[]
  remainingRedemptions: number | null
} | null>(null)
const couponError = ref('')
const applyingCoupon = ref(false)

// Multi-day events: one tab per day in date order, the all-days passes last, instead of one long
// scroll. A single group, or none dated, stays a flat list.
const ticketGroups = computed(() => groupTicketsByDay(ticketTypes.value))
const isMultiDayList = computed(() => ticketGroups.value.length > 1)
const useDayTabs = computed(() => isMultiDayList.value && event.value?.ticket_layout === 'tabs')
const activeDay = ref('')
let dayChosen = false
function selectDay(key: string) {
  dayChosen = true
  activeDay.value = key
}
// Open on the first day until the buyer picks one themselves.
watch(ticketGroups, (groups) => {
  if (!dayChosen || !groups.some((g) => g.key === activeDay.value)) activeDay.value = groups[0]?.key ?? ''
}, { immediate: true })
const visibleGroups = computed(() => (useDayTabs.value ? ticketGroups.value.filter((g) => g.key === activeDay.value) : ticketGroups.value))
const nextDayGroup = computed(() => {
  const groups = ticketGroups.value
  const i = groups.findIndex((g) => g.key === activeDay.value)
  return useDayTabs.value && i >= 0 ? groups[i + 1] : undefined
})
function dayCount(group: { items: TicketTypeSummary[] }) {
  return group.items.reduce((sum, type) => sum + (quantities.value[type.id] || 0), 0)
}
function scrollToSummary() {
  document.getElementById('order-summary')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
const selectedTypes = computed(() => ticketTypes.value.filter((type) => (quantities.value[type.id] || 0) > 0))
// Total ticket units across the whole cart (the "n tickets selected" bar). The coupon's own
// use limit counts only the tickets it discounts — see eligibleSelectedQuantity below.
const totalSelectedQuantity = computed(() =>
  selectedTypes.value.reduce((sum, type) => sum + (quantities.value[type.id] || 0), 0),
)

function decrementQty(type: TicketTypeSummary) {
  quantities.value[type.id] = Math.max(0, (quantities.value[type.id] || 0) - 1)
}

function incrementQty(type: TicketTypeSummary) {
  const next = (quantities.value[type.id] || 0) + 1
  quantities.value[type.id] = type.remaining === null ? next : Math.min(next, type.remaining)
}
const total = computed(() =>
  ticketTypes.value.reduce((sum, type) => sum + type.price * (quantities.value[type.id] || 0), 0),
)

// A coupon only ever discounts a coupon-eligible ticket type (TicketType.coupon_eligible), and
// only one it's itself allowed to touch — an empty allow-list means unrestricted, matching the
// backend's own Coupon.applies_to_ticket_type() exactly. An ineligible/disallowed type in the
// same cart is still charged in full (app/orders/routes.py's partial-discount logic).
function isEligibleForAppliedCoupon(type: TicketTypeSummary): boolean {
  if (!type.coupon_eligible) return false
  const allowed = appliedCoupon.value?.allowedTicketTypeIds ?? []
  return allowed.length === 0 || allowed.includes(type.id)
}
const eligibleSelectedTypes = computed(() => selectedTypes.value.filter(isEligibleForAppliedCoupon))
// Mirrors the backend's checkout-time redemption gate: only tickets the coupon discounts count as uses.
const eligibleSelectedQuantity = computed(() =>
  eligibleSelectedTypes.value.reduce((sum, type) => sum + (quantities.value[type.id] || 0), 0),
)
const eligibleSubtotal = computed(() =>
  eligibleSelectedTypes.value.reduce((sum, type) => sum + type.price * (quantities.value[type.id] || 0), 0),
)

// Mirrors the backend's own round-half-up-in-øre math (app/orders/routes.py) so the preview
// matches what checkout will actually charge — the backend still recomputes it authoritatively.
// Zero once exceedsRedemptionLimit is true: checkout will reject the coupon outright in that
// case (no partial application), so showing a discount here would be misleading.
const discountAmount = computed(() =>
  appliedCoupon.value && !exceedsRedemptionLimit.value
    ? Math.floor((eligibleSubtotal.value * appliedCoupon.value.discount_percent + 50) / 100)
    : 0,
)
const discountedTotal = computed(() => total.value - discountAmount.value)

// The adult/child cap only ever counts coupon-eligible tickets — an ineligible "adult" VIP
// ticket, say, gets no discount at all, so it shouldn't count against the cap either.
const couponAdultQty = computed(() =>
  eligibleSelectedTypes.value
    .filter((type) => type.age_category === 'adult')
    .reduce((sum, type) => sum + (quantities.value[type.id] || 0), 0),
)
const couponChildQty = computed(() =>
  eligibleSelectedTypes.value
    .filter((type) => type.age_category === 'child')
    .reduce((sum, type) => sum + (quantities.value[type.id] || 0), 0),
)
// Per-event limits (null = none), set in the admin event form — the backend enforces them at checkout.
const couponMaxAdult = computed(() => event.value?.coupon_max_adult ?? null)
const couponMaxChild = computed(() => event.value?.coupon_max_child ?? null)
const maxTicketsPerEmail = computed(() => event.value?.max_tickets_per_email ?? null)
const exceedsCouponLimit = computed(
  () =>
    !!appliedCoupon.value &&
    ((couponMaxAdult.value !== null && couponAdultQty.value > couponMaxAdult.value) ||
      (couponMaxChild.value !== null && couponChildQty.value > couponMaxChild.value)),
)
const couponLimitText = computed(() =>
  [
    couponMaxAdult.value !== null ? `${couponMaxAdult.value} adult` : null,
    couponMaxChild.value !== null ? `${couponMaxChild.value} child` : null,
  ]
    .filter(Boolean)
    .join(' and '),
)
// One email can reserve this many tickets of any one type — a quantity above it can never succeed.
const exceedsEmailLimit = computed(
  () =>
    maxTicketsPerEmail.value !== null &&
    selectedTypes.value.some((type) => (quantities.value[type.id] || 0) > maxTicketsPerEmail.value!),
)
const noEligibleSelection = computed(
  () => !!appliedCoupon.value && selectedTypes.value.length > 0 && eligibleSelectedTypes.value.length === 0,
)
// True once the coupon has fewer redemptions left than this cart would use — mirrors the
// backend's own checkout-time gate exactly, so the preview can warn (and block submit) up
// front instead of showing a full "applied"/"free" preview that checkout then rejects.
const exceedsRedemptionLimit = computed(
  () =>
    !!appliedCoupon.value &&
    appliedCoupon.value.remainingRedemptions !== null &&
    eligibleSelectedQuantity.value > appliedCoupon.value.remainingRedemptions,
)
// Either reason a currently-"applied" coupon actually has no effect on this cart.
const couponHasNoEffect = computed(() => noEligibleSelection.value || exceedsRedemptionLimit.value)

// A child ticket is never sold on its own — mirrors the backend's own rule (app/orders/routes.py),
// independent of any coupon.
const hasChildTicket = computed(() => selectedTypes.value.some((type) => type.age_category === 'child'))
const hasAdultTicket = computed(() => selectedTypes.value.some((type) => type.age_category === 'adult'))
const childWithoutAdult = computed(() => hasChildTicket.value && !hasAdultTicket.value)

// "Your details" (name/email/phone) sits well above the "Place order" button on this page —
// on a tall mobile screen a rejection there (e.g. the per-email ticket cap) is easy to miss
// once scrolled down to the button. Coupon errors are left out here since they already render
// right next to the button in the same summary card.
const detailsErrorMessages = computed(() =>
  [errors.value.customer_name, errors.value.customer_email, errors.value.customer_phone, errors.value.items, errors.value.form].filter(
    (message): message is string => !!message,
  ),
)

async function applyCoupon() {
  if (!event.value || !couponInput.value.trim()) return
  applyingCoupon.value = true
  couponError.value = ''
  try {
    const result = await validateCoupon(event.value.id, couponInput.value.trim())
    if (result.valid && result.discount_percent !== undefined) {
      appliedCoupon.value = {
        code: result.code ?? couponInput.value.trim().toUpperCase(),
        discount_percent: result.discount_percent,
        allowedTicketTypeIds: result.allowed_ticket_type_ids ?? [],
        remainingRedemptions: result.remaining_redemptions ?? null,
      }
    } else {
      appliedCoupon.value = null
      couponError.value = result.error || 'Invalid or inactive coupon code.'
    }
  } catch {
    appliedCoupon.value = null
    couponError.value = 'Could not check this coupon code. Please try again.'
  } finally {
    applyingCoupon.value = false
  }
}

function removeCoupon() {
  appliedCoupon.value = null
  couponInput.value = ''
  couponError.value = ''
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// Mirrors the backend's own check (app/orders/routes.py) for immediate feedback — the
// backend remains the authoritative validator regardless of what passes here.
function validateForm(): boolean {
  const validationErrors: Record<string, string> = {}
  if (!EMAIL_RE.test(form.value.customer_email.trim())) {
    validationErrors.customer_email = 'Enter a valid email address.'
  }
  if (!isValidPhone(form.value.customer_phone)) {
    validationErrors.customer_phone = phoneMessage()
  }
  errors.value = validationErrors
  return Object.keys(validationErrors).length === 0
}

onMounted(async () => {
  void fetchVippsAppConfig().then((cfg) => (vippsApp.value = cfg))
  void fetchStripeConfig().then((cfg) => (stripeCard.value = cfg))
  try {
    event.value = await fetchEvent(route.params.slug as string)
    const data = await fetchTicketTypes(event.value.id)
    ticketTypes.value = data.items
    for (const type of data.items) {
      quantities.value[type.id] = 0
    }
  } finally {
    loading.value = false
  }
})

// Display only — the backend computes the real fee and charges that.
const appFee = computed(() => vippsAppFee(discountedTotal.value, vippsApp.value.surcharge_percent))
const cardFee = computed(() => vippsAppFee(discountedTotal.value, stripeCard.value.surcharge_percent))
// Methods this event accepts right now. The backend already narrows the event's setting by
// whether Vipps App is on; the fallback keeps older responses working.
const methods = computed<('qr' | 'app' | 'bank' | 'cash' | 'card')[]>(
  () => event.value?.payment_methods ?? (vippsApp.value.enabled ? ['qr', 'app'] : ['qr']),
)
// If the preselected method is not on offer for this event, start on the first one that is.
watch(methods, (list) => {
  if (list.length && !list.includes(payMethod.value)) payMethod.value = list[0]
}, { immediate: true })
const showMethodChoice = computed(() => methods.value.length > 1 && discountedTotal.value > 0)
// The method actually used: the only one on offer, else the buyer's pick; nothing when it is free.
const chosenMethod = computed<'qr' | 'app' | 'bank' | 'cash' | 'card' | null>(() =>
  discountedTotal.value > 0 ? (methods.value.length === 1 ? methods.value[0] : payMethod.value) : null,
)
const usingApp = computed(() => chosenMethod.value === 'app')
const usingCard = computed(() => chosenMethod.value === 'card')
const onlineFee = computed(() => (usingCard.value ? cardFee.value : usingApp.value ? appFee.value : 0))
const usingCash = computed(() => chosenMethod.value === 'cash')
const usingBank = computed(() => chosenMethod.value === 'bank')

// A small pill beside the name when a ticket type cannot be bought right now (nothing when it is on sale).
function typePill(type: { status: string; sale_start: string | null }): { text: string; tone: string } | null {
  if (type.status === 'ended') return { text: 'Sales closed', tone: 'ds-badge-warning' }
  if (type.status === 'sold_out') return { text: 'Sold out', tone: 'ds-badge-neutral' }
  if (type.status === 'upcoming') {
    return { text: type.sale_start ? `Opens ${formatDateTime(type.sale_start)}` : 'Not open yet', tone: 'ds-badge-neutral' }
  }
  return null
}

async function submitOrder() {
  if (!event.value) return
  if (!validateForm()) return
  if (exceedsCouponLimit.value || exceedsEmailLimit.value || couponHasNoEffect.value || childWithoutAdult.value) return
  submitting.value = true
  let redirecting = false
  try {
    const items = ticketTypes.value
      .filter((type) => (quantities.value[type.id] || 0) > 0)
      .map((type) => ({ ticket_type_id: type.id, quantity: quantities.value[type.id] }))

    const result = await checkout({
      event_id: event.value.id,
      items,
      customer_name: form.value.customer_name,
      customer_email: form.value.customer_email,
      customer_phone: form.value.customer_phone.trim(),
      coupon_code: appliedCoupon.value?.code,
      payment_method: usingApp.value ? 'vipps_app' : usingCard.value ? 'stripe' : usingCash.value ? 'cash' : usingBank.value ? 'bank_transfer' : undefined,
    })
    if (result.redirect_url) {
      redirecting = true
      window.location.href = result.redirect_url
      return // stay in the "submitting" state while the browser leaves for Vipps
    }
    confirmedOrder.value = result
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      errors.value = { form: 'Could not place this order. Please try again.' }
    }
  } finally {
    if (!redirecting) submitting.value = false
  }
}

async function reportPayment() {
  if (!confirmedOrder.value) return
  reportingPayment.value = true
  try {
    confirmedOrder.value = await confirmPayment(confirmedOrder.value.order_number, confirmedOrder.value.customer_email)
  } finally {
    reportingPayment.value = false
  }
}
</script>

<template>
  <div class="ds-scope">
    <section class="ds-band ds-band-wash" style="padding-bottom: var(--ds-space-6)">
      <div class="ds-container">
        <BaseBreadcrumbs
          v-if="event"
          :items="[{ label: 'Events', to: '/events' }, { label: event.title, to: `/events/${event.slug}` }, { label: 'Tickets' }]"
          style="display: block; margin-bottom: var(--ds-space-5)"
        />
        <div class="ds-heading">
          <div style="display: flex; align-items: center; gap: var(--ds-space-3)">
            <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Tickets</span>
            <span v-if="event && !event.published" class="ds-badge ds-badge-neutral">Draft</span>
          </div>
          <h1 class="ds-display ds-display-m">{{ event?.title }}</h1>
          <p class="ds-intro">Choose your tickets and pay — we'll confirm and issue them shortly after.</p>
        </div>
      </div>
    </section>

    <section class="ds-band ds-band-paper" style="padding-top: var(--ds-space-6)">
      <div class="ds-container">
        <BaseLoadingState v-if="loading" label="Loading tickets…" />

        <div v-else-if="confirmedOrder" class="ds-row ds-row--sidebar">
          <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
            <span class="ds-badge ds-badge-success" style="align-self: flex-start">Order placed</span>
            <p class="ds-meta">Order number</p>
            <p class="ds-title">{{ confirmedOrder.order_number }}</p>
            <p class="ds-caption">{{ confirmedOrder.customer_email }}</p>
            <p class="ds-body">
              Status:
              <span class="ds-badge" :class="confirmedOrder.payment_status === 'pending_verification' ? 'ds-badge-accent' : 'ds-badge-neutral'">
                {{ paymentStatusLabel(confirmedOrder.payment_status) }}
              </span>
            </p>
            <p v-if="confirmedOrder.coupon_code" class="ds-caption">
              Coupon {{ confirmedOrder.coupon_code }} applied — saved {{ formatPrice(confirmedOrder.discount_amount) }}.
            </p>
            <p class="ds-meta">Save your order number and email — you'll need both to look up your tickets later.</p>
          </div>

          <div v-if="confirmedOrder.payment_status === 'paid'" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
            <h2 class="ds-subtitle">Tickets issued!</h2>
            <p class="ds-body">No payment was needed — we've emailed your QR-coded tickets to {{ confirmedOrder.customer_email }}.</p>
            <BaseButton
              type="button"
              variant="secondary"
              :to="`/orders/lookup?order_number=${confirmedOrder.order_number}&email=${encodeURIComponent(confirmedOrder.customer_email)}`"
            >
              View my tickets
            </BaseButton>
          </div>
          <CashPaymentPanel
            v-else-if="confirmedOrder.payment_method === 'cash'"
            :order-number="confirmedOrder.order_number"
            :total-amount="confirmedOrder.total_amount"
            :note="confirmedOrder.cash_note"
          />
          <BankPaymentPanel
            v-else-if="confirmedOrder.payment_method === 'bank_transfer'"
            :order-number="confirmedOrder.order_number"
            :total-amount="confirmedOrder.total_amount"
            :payment-status="confirmedOrder.payment_status"
            :bank="confirmedOrder.bank"
            :reporting="reportingPayment"
            @report="reportPayment"
          />
          <VippsPaymentPanel
            v-else
            :order-number="confirmedOrder.order_number"
            :total-amount="confirmedOrder.total_amount"
            :payment-status="confirmedOrder.payment_status"
            :reporting="reportingPayment"
            @report="reportPayment"
          />
        </div>

        <div v-else-if="event?.sales_closed" class="ds-alert ds-alert-warning sales-closed">
          <div>Ticket sales for this event have closed.</div>
        </div>

        <p v-else-if="event?.sales_not_open && event.sales_open_at" class="ds-sales-callout sales-not-open"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg><span><strong>Tickets on sale soon</strong> · Ticket sales open {{ formatDateTime(event.sales_open_at) }}</span></p>

        <BaseEmptyState
          v-else-if="ticketTypes.length === 0"
          title="No tickets available"
          description="This event doesn't have any ticket types set up yet."
        />

        <div v-else class="ds-row ds-row--sidebar">
          <div style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
            <nav v-if="useDayTabs" class="ds-tabs day-tabs" aria-label="Ticket days" style="flex-wrap: nowrap; overflow-x: auto; overflow-y: hidden; gap: var(--ds-space-5)">
              <button
                v-for="group in ticketGroups"
                :key="group.key"
                type="button"
                class="ds-tab day-tab"
                :class="{ 'ds-tab-active': activeDay === group.key }"
                :aria-current="activeDay === group.key ? 'true' : undefined"
                style="white-space: nowrap"
                @click="selectDay(group.key)"
              >
                {{ group.label }}<span v-if="dayCount(group)" class="day-tab-count" :aria-label="`${dayCount(group)} selected`"> · {{ dayCount(group) }}</span>
              </button>
            </nav>
            <template v-for="group in visibleGroups" :key="group.key">
            <h2 v-if="group.label && !useDayTabs" class="ds-subtitle ticket-day-heading" style="margin-top: var(--ds-space-2); color: var(--ds-terracotta-500); text-transform: uppercase">{{ group.label }}</h2>
            <div v-for="type in group.items" :key="type.id" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
              <div class="type-row" :class="{ 'type-row-pill': typePill(type) }" style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4)">
              <div style="display: flex; align-items: flex-start; gap: var(--ds-space-3); min-width: 0; flex: 1 1 auto">
                <TicketAgeIcon :category="type.age_category" :size="26" style="margin-top: 2px" />
                <div style="min-width: 0; overflow-wrap: anywhere" :style="type.status !== 'on_sale' ? 'opacity: 0.7' : ''">
                <p class="ds-body" style="font-weight: 600; display: flex; align-items: center; gap: var(--ds-space-2); flex-wrap: wrap; margin: 0">
                  {{ type.name }}
                </p>
                <p class="ds-meta">{{ formatPrice(type.price) }}</p>
                <p v-if="type.description" class="ds-caption" style="margin-top: 2px">{{ type.description }}</p>
                </div>
              </div>
              <span v-if="typePill(type)" class="ds-badge type-pill" :class="typePill(type)!.tone" style="font-weight: 400; flex-shrink: 0">{{ typePill(type)!.text }}</span>
              <span v-else style="display: inline-flex; align-items: center; gap: var(--ds-space-2); flex-shrink: 0">
                <BaseIconButton
                  label="Decrease quantity"
                  size="sm"
                  :disabled="type.status !== 'on_sale' || (quantities[type.id] || 0) <= 0"
                  @click="decrementQty(type)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /></svg>
                </BaseIconButton>
                <span class="ds-field-control" style="width: 56px">
                  <input
                    v-model.number="quantities[type.id]"
                    type="number"
                    min="0"
                    :disabled="type.status !== 'on_sale'"
                    class="ds-field-input ds-no-spinner"
                    style="text-align: center; padding: 13px 0"
                  />
                </span>
                <BaseIconButton
                  label="Increase quantity"
                  size="sm"
                  :disabled="type.status !== 'on_sale' || (type.remaining !== null && (quantities[type.id] || 0) >= type.remaining)"
                  @click="incrementQty(type)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
                </BaseIconButton>
              </span>
              </div>
            </div>
            </template>
            <BaseButton v-if="nextDayGroup" type="button" variant="secondary" class="next-day-nudge" @click="selectDay(nextDayGroup.key)">
              {{ nextDayGroup.key === 'all' ? 'Or get an all-days pass' : `More happening on ${nextDayGroup.label}` }} →
            </BaseButton>

            <div v-if="childWithoutAdult" class="ds-alert ds-alert-danger">
              <div>A child ticket can't be purchased on its own — please add at least one adult ticket.</div>
            </div>

            <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
              <h2 class="ds-subtitle">Your details</h2>
              <label class="ds-field">
                <span class="ds-field-label">Full name</span>
                <span class="ds-field-control" :class="{ 'ds-field-control-error': errors.customer_name }">
                  <input v-model="form.customer_name" type="text" placeholder="Full name" class="ds-field-input" />
                </span>
                <span v-if="errors.customer_name" class="ds-field-error-text">{{ errors.customer_name }}</span>
              </label>
              <label class="ds-field">
                <span class="ds-field-label">Email</span>
                <span class="ds-field-control" :class="{ 'ds-field-control-error': errors.customer_email }">
                  <input v-model="form.customer_email" type="email" placeholder="Email address" class="ds-field-input" />
                </span>
                <span v-if="errors.customer_email" class="ds-field-error-text">{{ errors.customer_email }}</span>
                <span v-if="maxTicketsPerEmail !== null" class="ds-caption email-limit-hint">
                  Up to {{ maxTicketsPerEmail }} tickets of each type per email address.
                </span>
                <span v-if="exceedsEmailLimit" class="ds-field-error-text">
                  You can reserve at most {{ maxTicketsPerEmail }} tickets of each type per email address.
                </span>
              </label>
              <label class="ds-field">
                <span class="ds-field-label">Phone</span>
                <span class="ds-field-control" :class="{ 'ds-field-control-error': errors.customer_phone }">
                  <input v-model="form.customer_phone" type="text" placeholder="Phone" class="ds-field-input" />
                </span>
                <span v-if="errors.customer_phone" class="ds-field-error-text">{{ errors.customer_phone }}</span>
              </label>
              <div v-if="errors.form" class="ds-alert ds-alert-danger"><div>{{ errors.form }}</div></div>
            </div>
          </div>

          <aside id="order-summary" class="ds-card" style="position: sticky; top: calc(var(--ds-nav-height) + var(--ds-space-5)); display: flex; flex-direction: column; gap: var(--ds-space-3)">
            <h2 class="ds-subtitle">Order summary</h2>
            <BaseEmptyState v-if="selectedTypes.length === 0" title="No tickets selected" description="Choose a quantity above." />
            <div v-for="type in selectedTypes" :key="type.id" class="ds-deflist-row" style="padding: var(--ds-space-2) 0; border-bottom: 1px solid var(--ds-border-hairline)">
              <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-1); display: flex; align-items: center; gap: var(--ds-space-2)"><TicketAgeIcon :category="type.age_category" :size="16" />{{ quantities[type.id] }} × {{ type.name }}</p>
              <p class="ds-body">{{ formatPrice(type.price * quantities[type.id]) }}</p>
              <p v-if="appliedCoupon && !isEligibleForAppliedCoupon(type)" class="ds-caption">
                Not eligible for the coupon discount — charged in full.
              </p>
            </div>

            <div v-if="couponsOn && !appliedCoupon" style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
              <label class="ds-field">
                <span class="ds-field-label">Coupon code (optional)</span>
                <span style="display: flex; gap: var(--ds-space-2)">
                  <span class="ds-field-control" style="flex: 1"><input v-model="couponInput" type="text" placeholder="SAVE20" class="ds-field-input" style="text-transform: uppercase" /></span>
                  <BaseButton type="button" variant="secondary" size="sm" :disabled="applyingCoupon || !couponInput.trim()" @click="applyCoupon">
                    {{ applyingCoupon ? 'Checking…' : 'Apply' }}
                  </BaseButton>
                </span>
                <span v-if="couponError" class="ds-field-error-text">{{ couponError }}</span>
              </label>
            </div>
            <div
              v-else-if="appliedCoupon"
              class="ds-alert"
              :class="couponHasNoEffect ? 'ds-alert-warning' : 'ds-alert-success'"
              style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-2)"
            >
              <div v-if="noEligibleSelection">
                Coupon <strong>{{ appliedCoupon.code }}</strong> is valid but doesn't apply to your current selection.
              </div>
              <div v-else-if="exceedsRedemptionLimit">
                Coupon <strong>{{ appliedCoupon.code }}</strong> only has {{ appliedCoupon.remainingRedemptions }}
                use(s) left — you're requesting {{ eligibleSelectedQuantity }}.
              </div>
              <div v-else>Coupon <strong>{{ appliedCoupon.code }}</strong> applied ({{ appliedCoupon.discount_percent }}% off).</div>
              <BaseButton type="button" variant="ghost" size="sm" @click="removeCoupon">Remove</BaseButton>
            </div>
            <p v-if="exceedsCouponLimit" class="ds-field-error-text">
              An order using a coupon can include at most {{ couponLimitText }} coupon-eligible tickets.
            </p>
            <p v-if="noEligibleSelection" class="ds-field-error-text">
              None of your selected ticket types are eligible for this coupon.
            </p>
            <p v-if="exceedsRedemptionLimit" class="ds-field-error-text">
              Reduce your ticket quantity to {{ appliedCoupon?.remainingRedemptions }} or fewer, or remove the coupon.
            </p>
            <p v-if="errors.coupon_code" class="ds-field-error-text">{{ errors.coupon_code }}</p>

            <div v-if="appliedCoupon" class="ds-deflist-row" style="padding: var(--ds-space-2) 0; border-bottom: 1px solid var(--ds-border-hairline)">
              <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-1)">Discount</p>
              <p class="ds-body">-{{ formatPrice(discountAmount) }}</p>
            </div>
            <p class="ds-title" style="margin-top: var(--ds-space-2)">Total: {{ formatPrice(discountedTotal) }}</p>
            <p v-if="appliedCoupon && discountedTotal === 0" class="ds-meta">
              Free with this coupon — your tickets will be issued immediately, no payment needed.
            </p>
            <div v-if="detailsErrorMessages.length" class="ds-alert ds-alert-danger">
              <div>
                <p v-for="(message, index) in detailsErrorMessages" :key="index" style="margin: 0">{{ message }}</p>
              </div>
            </div>
            <div v-if="showMethodChoice" class="ds-field" role="radiogroup" aria-label="Payment method" style="display: grid; gap: var(--ds-space-2)">
              <p class="ds-eyebrow">Pay with</p>
              <label v-if="methods.includes('qr')" class="tp-choice" :class="{ 'tp-choice-on': payMethod === 'qr' }">
                <input v-model="payMethod" type="radio" name="tp-pay" value="qr" class="tp-sr" />
                <span class="tp-radio" aria-hidden="true"><span v-if="payMethod === 'qr'" class="tp-radio-dot"></span></span>
                <span><span class="tp-choice-title">Vipps-QR</span><span class="ds-meta" style="display: block">Pay after placing your order</span></span>
              </label>
              <label v-if="methods.includes('app')" class="tp-choice" :class="{ 'tp-choice-on': payMethod === 'app' }">
                <input v-model="payMethod" type="radio" name="tp-pay" value="app" class="tp-sr" />
                <span class="tp-radio" aria-hidden="true"><span v-if="payMethod === 'app'" class="tp-radio-dot"></span></span>
                <span><span class="tp-choice-title">Vipps-App</span><span class="ds-meta" style="display: block">Pay directly in the Vipps App<br />(Convenience fee +{{ vippsApp.surcharge_percent }}%)</span></span>
              </label>
              <label v-if="methods.includes('card')" class="tp-choice" :class="{ 'tp-choice-on': payMethod === 'card' }">
                <input v-model="payMethod" type="radio" name="tp-pay" value="card" class="tp-sr" />
                <span class="tp-radio" aria-hidden="true"><span v-if="payMethod === 'card'" class="tp-radio-dot"></span></span>
                <span><span class="tp-choice-title">Card</span><span class="ds-meta" style="display: block">Pay by card on a secure page<template v-if="stripeCard.surcharge_percent"><br />(Convenience fee +{{ stripeCard.surcharge_percent }}%)</template></span></span>
              </label>
              <label v-if="methods.includes('bank')" class="tp-choice" :class="{ 'tp-choice-on': payMethod === 'bank' }">
                <input v-model="payMethod" type="radio" name="tp-pay" value="bank" class="tp-sr" />
                <span class="tp-radio" aria-hidden="true"><span v-if="payMethod === 'bank'" class="tp-radio-dot"></span></span>
                <span><span class="tp-choice-title">Bank transfer</span><span class="ds-meta" style="display: block">Transfer after placing your order</span></span>
              </label>
              <label v-if="methods.includes('cash')" class="tp-choice" :class="{ 'tp-choice-on': payMethod === 'cash' }">
                <input v-model="payMethod" type="radio" name="tp-pay" value="cash" class="tp-sr" />
                <span class="tp-radio" aria-hidden="true"><span v-if="payMethod === 'cash'" class="tp-radio-dot"></span></span>
                <span><span class="tp-choice-title">Cash</span><span class="ds-meta" style="display: block">Pay in person after placing your order</span></span>
              </label>
            </div>
            <div v-if="usingCash" class="ds-alert ds-alert-info cash-note-preview">
              <div style="white-space: pre-line">{{ event?.cash_note || 'Pay in cash to the association. Your order is confirmed once we have received the payment.' }}</div>
            </div>
            <div v-if="(usingApp || usingCard) && onlineFee > 0" class="ds-meta vipps-app-fee" style="display: grid; grid-template-columns: 1fr auto; gap: 2px 12px">
              <span>Convenience fee</span><span>{{ formatPrice(onlineFee) }}</span>
              <strong>Total to pay</strong><strong>{{ formatPrice(discountedTotal + onlineFee) }}</strong>
            </div>
            <BaseButton
              type="button"
              variant="primary"
              full-width
              class="submit-order"
              :disabled="submitting || selectedTypes.length === 0 || exceedsCouponLimit || exceedsEmailLimit || couponHasNoEffect || childWithoutAdult"
              @click="submitOrder"
            >
              {{ submitting ? (usingApp ? 'Opening Vipps…' : usingCard ? 'Opening the card page…' : 'Placing order…') : usingApp ? `Pay ${formatPrice(discountedTotal + appFee)} with Vipps` : usingCard ? `Pay ${formatPrice(discountedTotal + cardFee)} by card` : 'Place order' }}
            </BaseButton>
          </aside>
        </div>
      </div>
    </section>

    <div v-if="isMultiDayList && totalSelectedQuantity > 0" class="mobile-order-bar ds-scope">
      <span class="ds-body" style="font-weight: 600">{{ totalSelectedQuantity }} {{ totalSelectedQuantity === 1 ? 'ticket' : 'tickets' }} selected</span>
      <BaseButton type="button" variant="primary" size="sm" class="review-order" @click="scrollToSummary">Review order ↓</BaseButton>
    </div>
  </div>
</template>

<style scoped>
.ds-no-spinner::-webkit-outer-spin-button,
.ds-no-spinner::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.ds-no-spinner {
  -moz-appearance: textfield;
}
/* Phones: a bar pinned to the bottom keeps the cart in view while browsing day tabs. */
.mobile-order-bar { display: none; }
@media (max-width: 900px) {
  .mobile-order-bar {
    display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-3);
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 30;
    padding: var(--ds-space-3) var(--ds-space-4);
    background: var(--ds-surface-card); border-top: 1px solid var(--ds-border-default);
  }
}
.day-tab-count { color: var(--ds-terracotta-500); }
.next-day-nudge { align-self: flex-start; }
@media (max-width: 640px) {
  .next-day-nudge { align-self: stretch; width: 100%; justify-content: center; }
}
/* On phones the pill folds under the ticket name (right-aligned) instead of squeezing it. */
@media (max-width: 480px) {
  .type-row-pill { flex-wrap: wrap; }
  .type-row-pill > :first-child { flex: 1 1 100%; }
  .type-row-pill .type-pill { margin-left: auto; }
}
</style>

<style scoped>
.tp-choice { position: relative; display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: 12px; padding: 12px 14px; border-radius: var(--ds-radius-md); cursor: pointer; background: var(--ds-surface-card); border: 1px solid var(--ds-border-default); transition: all 0.15s; }
.tp-choice-on { background: var(--ds-surface-accent-soft); border-color: var(--ds-border-primary); box-shadow: 0 0 0 1px var(--ds-border-primary); }
.tp-choice-title { font-weight: 600; color: var(--ds-text-heading); }
.tp-radio { width: 18px; height: 18px; border-radius: 999px; border: 1.5px solid var(--ds-border-strong); display: grid; place-items: center; }
.tp-choice-on .tp-radio { border-color: var(--ds-action-primary); }
.tp-radio-dot { width: 9px; height: 9px; border-radius: 999px; background: var(--ds-action-primary); }
.tp-sr { position: absolute; top: 0; left: 0; width: 1px; height: 1px; margin: 0; padding: 0; border: 0; overflow: hidden; clip: rect(0 0 0 0); clip-path: inset(50%); opacity: 0; pointer-events: none; }
</style>
