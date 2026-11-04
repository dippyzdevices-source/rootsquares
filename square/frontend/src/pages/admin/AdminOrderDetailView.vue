<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'
import { moduleEnabled } from '../../services/modules'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import BaseAvatarLabel from '../../components/ui/BaseAvatarLabel.vue'
import { humanize } from '../../utils/formatEnum'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseRadio from '../../components/ui/BaseRadio.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import { fetchAdminOrder, markOrderPaid, rejectOrder, cancelOrder, resendConfirmation, type AdminOrder } from '../../services/adminOrdersApi'
import { formatPrice } from '../../utils/money'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: ticketStatusLabel } = useLookup('ticket_status')
const { label: providerLabel } = useLookup('payment_provider')
const { label: paymentStatusLabel } = useLookup('payment_status')
const route = useRoute()
const toast = useToast()

const orderId = computed(() => Number(route.params.id))
const order = ref<AdminOrder | null>(null)
const loading = ref(true)
const marking = ref(false)
const rejecting = ref(false)
const showRejectModal = ref(false)
const rejectReason = ref('')
const rejectError = ref('')
const cancelling = ref(false)
const resending = ref(false)
const showCancelModal = ref(false)
const cancelReason = ref('')
const cancelError = ref('')

async function load() {
  loading.value = true
  try {
    order.value = await fetchAdminOrder(orderId.value)
  } catch {
    toast.error('Could not load this order')
  } finally {
    loading.value = false
  }
}

// How the money actually arrived. Starts on how the order was placed (cash, else Vipps-QR) so the
// admin only changes it when the buyer paid another way.
// Member / former member / guest, with the membership type for the first two.
const membersOn = moduleEnabled('members') // W8-R19: no member / guest label without the Members module
const customerPill = computed(() => {
  const info = order.value?.customer_member
  const type = info?.membership_type ? ` · ${humanize(info.membership_type)}` : ''
  if (info?.status === 'member') return { text: `Member${type}`, tone: 'ds-badge-success' }
  if (info?.status === 'former') return { text: `Former member${type}`, tone: 'ds-badge-neutral' }
  return { text: 'Guest', tone: 'ds-badge-neutral' }
})
// A paid order nobody approved: either a coupon covered everything (no payment row at all) or the
// Vipps-App confirmed it by itself. Both get the same green banner and Payments row as an approved one.
// "Coupon BCAMEMBER26 (100% off)" — the percentage is shown when the coupon is still known.
const couponLabel = computed(() => {
  const o = order.value
  if (!o?.coupon_code) return ''
  return o.coupon_percent ? `Coupon ${o.coupon_code} (${o.coupon_percent}% off)` : `Coupon ${o.coupon_code}`
})
const hasCheckedInTicket = computed(() =>
  (order.value?.items ?? []).some((item) => item.tickets.some((t) => t.status === 'used')),
)
// The extra fee the customer paid on top of the order total (Vipps-App), from payments that count.
const convenienceFee = computed(() =>
  (order.value?.payments ?? [])
    .filter((p) => !['failed', 'cancelled'].includes(p.status))
    .reduce((sum, p) => sum + (p.surcharge_amount || 0), 0),
)
// An order with a payment that counts always shows the fee and total-charged lines (a zero fee for QR, which the customer is not charged).
const hasCountingPayment = computed(() =>
  (order.value?.payments ?? []).some((p) => !['failed', 'cancelled'].includes(p.status)),
)
// The mode the customer paid (or is paying) with: the paid payment, else the latest one that counts.
const paymentMode = computed(() => {
  const o = order.value
  if (!o) return ''
  if (paidWithCouponOnly.value) return 'Coupon (no payment needed)'
  const live = (o.payments ?? []).filter((p) => !['failed', 'cancelled'].includes(p.status))
  const chosen = live.find((p) => p.status === 'paid') ?? live[0]
  return chosen ? providerLabel(chosen.provider) : ''
})
const ticketsSubtotal = computed(() => (order.value?.items ?? []).reduce((sum, item) => sum + item.subtotal, 0))
const paidWithCouponOnly = computed(() => {
  const o = order.value
  return !!o && o.payment_status === 'paid' && !(o.payments && o.payments.length) && !!o.coupon_code && o.total_amount === 0
})
const paidAutomatically = computed(() => {
  const o = order.value
  return !!o && o.payment_status === 'paid' && !o.approved_by_name && !o.approved_by_email && ['vipps_app', 'stripe'].includes(o.payments?.[0]?.provider ?? '')
})
const awaitingPaymentAction = computed(
  () => order.value?.payment_status === 'pending' || order.value?.payment_status === 'pending_verification',
)
const paidWith = ref<'cash' | 'vipps_qr' | 'bank_transfer'>('vipps_qr')
watch(order, (o) => {
  const placedWith = o?.payments?.[0]?.provider
  paidWith.value = placedWith === 'cash' || placedWith === 'bank_transfer' ? placedWith : 'vipps_qr'
})
const paidWithOptions = computed(() => [
  { value: 'cash', label: providerLabel('cash') },
  { value: 'vipps_qr', label: providerLabel('vipps_qr') },
  { value: 'bank_transfer', label: providerLabel('bank_transfer') },
])

async function resendEmail() {
  resending.value = true
  try {
    const { sent_to } = await resendConfirmation(orderId.value)
    toast.success(`Confirmation email sent to ${sent_to}`)
  } catch {
    toast.error('Could not send the confirmation email')
  } finally {
    resending.value = false
  }
}

async function markPaid() {
  marking.value = true
  try {
    order.value = await markOrderPaid(orderId.value, paidWith.value)
    toast.success('Order marked as paid')
  } catch {
    toast.error('Could not mark this order as paid')
  } finally {
    marking.value = false
  }
}

function openRejectModal() {
  rejectReason.value = ''
  rejectError.value = ''
  showRejectModal.value = true
}

async function confirmReject() {
  if (!rejectReason.value.trim()) {
    rejectError.value = 'This field is required.'
    return
  }
  rejecting.value = true
  try {
    order.value = await rejectOrder(orderId.value, rejectReason.value.trim())
    showRejectModal.value = false
    toast.success('Order rejected')
  } catch {
    toast.error('Could not reject this order')
  } finally {
    rejecting.value = false
  }
}

function openCancelModal() {
  cancelReason.value = ''
  cancelError.value = ''
  showCancelModal.value = true
}

async function confirmCancel() {
  if (!cancelReason.value.trim()) {
    cancelError.value = 'This field is required.'
    return
  }
  cancelling.value = true
  try {
    order.value = await cancelOrder(orderId.value, cancelReason.value.trim())
    showCancelModal.value = false
    toast.success('Order cancelled')
  } catch {
    toast.error('Could not cancel this order')
  } finally {
    cancelling.value = false
  }
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString()
}

function statusTone(value: string): string {
  if (value === 'paid') return 'ds-badge-success'
  if (value === 'failed' || value === 'cancelled' || value === 'rejected') return 'ds-badge-danger'
  if (value === 'refunded') return 'ds-badge-info'
  if (value === 'pending_verification') return 'ds-badge-accent'
  return 'ds-badge-neutral'
}

onMounted(load)
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
    <BaseLoadingState v-if="loading" label="Loading order…" />
    <template v-else-if="order">
      <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">Orders</h1>
        </div>
        <BaseButton type="button" to="/admin/orders" variant="secondary" size="sm">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
          Back
        </BaseButton>
      </div>

      <hr class="ds-section-line" />

      <div style="max-width: 620px; display: flex; flex-direction: column; gap: var(--ds-space-5)">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
          <h2 class="ds-display ds-display-s">Order {{ order.order_number }}</h2>
          <span class="ds-badge" :class="statusTone(order.payment_status)">{{ paymentStatusLabel(order.payment_status) }}</span>
        </div>
        <div class="ds-caption">
          <div>Placed {{ formatDateTime(order.created_at) }}</div>
          <div v-if="order.updated_at && order.updated_at !== order.created_at">Last updated {{ formatDateTime(order.updated_at) }}</div>
        </div>

      <div v-if="order.payment_status === 'paid' && (order.approved_by_name || order.approved_by_email)" class="ds-alert ds-alert-success">
        <div>
          <strong class="ds-alert-title">Marked as paid</strong>
          <BaseAvatarLabel
            :name="order.approved_by_name"
            :email="order.approved_by_email"
            style="margin-top: var(--ds-space-1)"
          />
          <div class="ds-caption" style="margin-top: var(--ds-space-1)">on {{ formatDateTime(order.approved_at!) }}</div>
        </div>
      </div>

      <div v-else-if="paidWithCouponOnly" class="ds-alert ds-alert-success paid-banner">
        <div>
          <strong class="ds-alert-title">Paid with coupon</strong>
          <p class="ds-body" style="margin: var(--ds-space-1) 0 0">{{ couponLabel }}</p>
          <div class="ds-caption" style="margin-top: var(--ds-space-1)">on {{ formatDateTime(order.created_at) }}</div>
        </div>
      </div>

      <div v-else-if="paidAutomatically" class="ds-alert ds-alert-success paid-banner">
        <div>
          <strong class="ds-alert-title">Paid with {{ providerLabel(order.payments![0].provider) }}</strong>
          <p class="ds-body" style="margin: var(--ds-space-1) 0 0">Confirmed automatically</p>
          <div class="ds-caption" style="margin-top: var(--ds-space-1)">on {{ formatDateTime(order.payments![0].paid_at ?? order.created_at) }}</div>
        </div>
      </div>

      <div v-if="order.payment_status === 'rejected'" class="ds-alert ds-alert-danger">
        <div>
          <strong class="ds-alert-title">Rejected</strong>
          <template v-if="order.rejected_by_name || order.rejected_by_email">
            <BaseAvatarLabel
              :name="order.rejected_by_name"
              :email="order.rejected_by_email"
              style="margin-top: var(--ds-space-1)"
            />
            <div class="ds-caption" style="margin-top: var(--ds-space-1)">on {{ formatDateTime(order.rejected_at!) }}</div>
          </template>
          <div v-if="order.rejection_reason" style="margin-top: var(--ds-space-1)">Reason: {{ order.rejection_reason }}</div>
        </div>
      </div>

      <div v-if="order.payment_status === 'cancelled'" class="ds-alert ds-alert-danger">
        <div>
          <strong class="ds-alert-title">Cancelled</strong>
          <template v-if="order.cancelled_by_name || order.cancelled_by_email">
            <BaseAvatarLabel
              :name="order.cancelled_by_name"
              :email="order.cancelled_by_email"
              style="margin-top: var(--ds-space-1)"
            />
            <div class="ds-caption" style="margin-top: var(--ds-space-1)">on {{ formatDateTime(order.cancelled_at!) }}</div>
          </template>
          <div v-if="order.cancellation_reason" style="margin-top: var(--ds-space-1)">Reason: {{ order.cancellation_reason }}</div>
        </div>
      </div>

      <div class="ds-card order-customer" style="display: flex; justify-content: space-between; align-items: flex-start; gap: var(--ds-space-3) var(--ds-space-4); flex-wrap: wrap">
        <div style="flex: 1 1 14rem; min-width: 0">
          <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-2)">Customer</p>
          <p class="ds-body" style="font-weight: 600; display: flex; align-items: center; gap: var(--ds-space-2); flex-wrap: wrap; margin: 0">
            <router-link v-if="membersOn && order.customer_member?.member_id" :to="`/admin/members/${order.customer_member.member_id}`" class="member-link" style="font-weight: 600">{{ order.customer_name }}</router-link>
            <template v-else>{{ order.customer_name }}</template>
          </p>
          <p class="ds-meta" style="overflow-wrap: anywhere">{{ order.customer_email }}</p>
          <p v-if="order.customer_phone" class="ds-meta">{{ order.customer_phone }}</p>
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: var(--ds-space-2); flex-shrink: 0; margin-left: auto">
          <BaseAvatar class="customer-avatar" :src="order.customer_member?.photo_url" :name="order.customer_name" size="lg" />
          <span v-if="membersOn" class="ds-badge customer-pill" :class="customerPill.tone">{{ customerPill.text }}</span>
        </div>
      </div>

      <div class="ds-card order-tickets" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-eyebrow">Tickets</p>
        <div
          v-for="(item, itemIndex) in order.items"
          :key="item.id"
          :style="itemIndex > 0 ? 'padding-top: var(--ds-space-4); border-top: 1px solid var(--ds-border-hairline)' : ''"
        >
        <p class="ds-meta">{{ item.quantity }} × {{ item.ticket_type_name }}</p>
        <div v-if="item.tickets.length" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: var(--ds-space-3); margin-top: var(--ds-space-3)">
          <div v-for="ticket in item.tickets" :key="ticket.id" style="text-align: center">
            <div style="position: relative; margin: 0 auto; width: 128px">
              <img
                :src="ticket.qr_code_data_url"
                :alt="ticket.ticket_code"
                style="width: 128px"
                :style="ticket.status !== 'valid' ? 'opacity: 0.3' : ''"
              />
              <div v-if="ticket.status === 'used' || ticket.status === 'void'" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center">
                <span
                  style="display: flex; height: 40px; width: 40px; align-items: center; justify-content: center; border-radius: 999px; color: white; font-size: 20px"
                  :style="ticket.status === 'used' ? 'background: var(--ds-status-success)' : 'background: var(--ds-status-danger)'"
                >
                  {{ ticket.status === 'used' ? '✓' : '✕' }}
                </span>
              </div>
            </div>
            <p class="ds-caption" style="margin: var(--ds-space-3) 0 0; font-family: monospace; word-break: break-all;">{{ ticket.ticket_code }}</p>
            <p v-if="ticket.issued_at" class="ds-caption" style="margin: var(--ds-space-1) 0 0">Issued {{ formatDateTime(ticket.issued_at) }}</p>
            <span
              class="ds-badge"
              :class="ticket.status === 'used' ? 'ds-badge-neutral' : ticket.status === 'void' ? 'ds-badge-danger' : 'ds-badge-success'"
              style="margin-top: var(--ds-space-3)"
            >
              {{ ticketStatusLabel(ticket.status) }}
            </span>
            <div v-if="ticket.status === 'used' && ticket.checked_in_at" style="display: flex; flex-direction: column; align-items: center; gap: var(--ds-space-1); margin-top: var(--ds-space-2)">
              <p class="ds-caption" style="margin: 0">Checked in by</p>
              <div style="display: inline-flex">
                <BaseAvatarLabel :name="ticket.checked_in_by_name" :email="ticket.checked_in_by_email" />
              </div>
              <div class="ds-caption">{{ formatDateTime(ticket.checked_in_at) }}</div>
            </div>
          </div>
        </div>
      </div>
      </div>

      <div class="ds-card order-payments" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-3)">
          <p class="ds-eyebrow" style="margin: 0">Payments</p>
          <span v-if="paymentMode" class="ds-badge ds-badge-info order-payment-mode">Payment mode: {{ paymentMode }}</span>
        </div>
        <div class="order-total" style="display: flex; flex-direction: column; gap: var(--ds-space-2); padding-bottom: var(--ds-space-3); border-bottom: 1px solid var(--ds-border-hairline)">
          <p v-for="item in order.items" :key="`line-${item.id}`" class="ds-meta order-line" style="margin: 0; display: flex; justify-content: space-between; gap: var(--ds-space-3)">
            <span>{{ item.quantity }} × {{ item.ticket_type_name }}</span><span>{{ formatPrice(item.subtotal) }}</span>
          </p>
          <template v-if="order.coupon_code || order.discount_amount">
            <p class="ds-body order-subtotal" style="margin: 0; display: flex; justify-content: space-between; gap: var(--ds-space-3)">
              <span>Subtotal</span><span>{{ formatPrice(ticketsSubtotal) }}</span>
            </p>
            <p class="ds-meta order-discount" style="margin: 0; display: flex; justify-content: space-between; gap: var(--ds-space-3)">
              <span>{{ couponLabel }}</span><span>−{{ formatPrice(order.discount_amount) }}</span>
            </p>
          </template>
          <p class="ds-body order-total-line" style="margin: 0; display: flex; justify-content: space-between; gap: var(--ds-space-3); font-weight: 700">
            <span>Total</span><span>{{ formatPrice(order.total_amount) }}</span>
          </p>
          <template v-if="hasCountingPayment">
            <p class="ds-meta order-fee" style="margin: 0; display: flex; justify-content: space-between; gap: var(--ds-space-3)">
              <span>Payment fee</span><span>{{ formatPrice(convenienceFee) }}</span>
            </p>
            <p class="ds-body order-charged" style="margin: 0; display: flex; justify-content: space-between; gap: var(--ds-space-3); font-weight: 700">
              <span>Total charged</span><span>{{ formatPrice(order.total_amount + convenienceFee) }}</span>
            </p>
          </template>
        </div>
        <div v-if="paidWithCouponOnly" class="order-payment-row coupon-payment-row" style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-3); flex-wrap: wrap">
          <span>
            <span style="font-weight: 600">{{ couponLabel }}</span>
            <span class="ds-caption" style="display: block">
              <span style="display: block">Covered the full amount</span>
              <span style="display: block">{{ formatPrice(order.discount_amount) }} off</span>
              <span style="display: block">No payment needed</span>
              <span style="display: block">Applied {{ formatDateTime(order.created_at) }}</span>
            </span>
          </span>
          <span class="ds-badge" :class="statusTone(order.payment_status)">{{ paymentStatusLabel(order.payment_status) }}</span>
        </div>
        <div v-for="payment in order.payments" :key="payment.id" class="order-payment-row" style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-3); flex-wrap: wrap">
          <span>
            <router-link :to="{ path: '/admin/payments', query: { q: payment.payment_reference ?? '' } }" class="payment-link" style="font-weight: 600">{{ payment.payment_reference ?? `Payment ${payment.id}` }}</router-link>
            <span class="ds-caption" style="display: block">
              {{ providerLabel(payment.provider) }} · {{ formatPrice(payment.amount) }}<template v-if="payment.surcharge_amount"> (incl. {{ formatPrice(payment.surcharge_amount) }} fee)</template>
            </span>
            <span class="ds-caption" style="display: block">
              <span style="display: block">Created {{ formatDateTime(payment.created_at) }}</span>
              <span v-if="payment.paid_at || payment.status === 'paid'" style="display: block">Paid {{ formatDateTime(payment.paid_at ?? payment.updated_at ?? payment.created_at) }}</span>
              <span v-if="payment.processing_fee_amount && order.payment_status === 'paid' && !['failed', 'cancelled'].includes(payment.status)" class="payment-processing-fee" style="display: block">
                Processing fee {{ formatPrice(payment.processing_fee_amount) }}<template v-if="!payment.surcharge_amount"> · absorbed by {{ squareProfile.name }}, not charged to the customer</template><template v-else> · taken from the amount charged</template>
              </span>
              <span v-if="payment.updated_at && !payment.paid_at && payment.status !== 'paid' && payment.updated_at !== payment.created_at" style="display: block">Updated {{ formatDateTime(payment.updated_at) }}</span>
            </span>
          </span>
          <span class="ds-badge" :class="statusTone(payment.status)">{{ paymentStatusLabel(payment.status) }}</span>
        </div>
        <div
          v-if="awaitingPaymentAction"
          class="order-actions"
          style="display: flex; flex-direction: column; gap: var(--ds-space-3); padding-top: var(--ds-space-3); border-top: 1px solid var(--ds-border-hairline)"
        >
          <div class="paid-with" role="radiogroup" aria-label="Paid with" style="display: flex; gap: var(--ds-space-5); align-items: center; justify-content: center; flex-wrap: wrap">
            <BaseRadio
              v-for="option in paidWithOptions"
              :key="option.value"
              v-model="paidWith"
              name="paid-with"
              :value="option.value"
              :label="option.label"
            />
          </div>
          <hr class="ds-section-line" style="margin: 0" />
          <div class="order-action-buttons" style="display: flex; justify-content: center; flex-wrap: wrap; gap: var(--ds-space-3)">
            <BaseButton
              type="button"
              variant="success"
              class="mark-paid"
              style="min-width: 160px"
              :disabled="marking || rejecting"
              @click="markPaid"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
              {{ marking ? 'Marking as paid…' : 'Mark as paid' }}
            </BaseButton>
            <BaseButton
              type="button"
              variant="danger"
              class="reject-order"
              style="min-width: 160px"
              :disabled="marking || rejecting"
              @click="openRejectModal"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>
              Reject
            </BaseButton>
          </div>
        </div>
      </div>

      <div v-if="order.payment_status === 'paid'">
        <div class="order-actions">
        <BaseButton type="button" variant="secondary" class="resend-confirmation" :disabled="resending" @click="resendEmail">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 7-10 6L2 7" /></svg>
          {{ resending ? 'Sending…' : 'Resend confirmation email' }}
        </BaseButton>
        <BaseButton
          type="button"
          variant="danger"
          class="cancel-order"
          :disabled="cancelling || hasCheckedInTicket"
          @click="openCancelModal"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10" /><path d="m4.9 4.9 14.2 14.2" /></svg>
          {{ cancelling ? 'Cancelling…' : 'Cancel order' }}
        </BaseButton>
        </div>
        <p v-if="hasCheckedInTicket" class="ds-caption cancel-blocked" style="margin-top: var(--ds-space-2)">
          Can't cancel: a ticket on this order has already been checked in.
        </p>
      </div>
      </div>
    </template>

    <BaseModal v-model="showRejectModal" title="Reject this order">
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Reason for rejection</span>
          <span class="ds-field-control" :class="{ 'ds-field-control-error': rejectError }">
            <textarea v-model="rejectReason" rows="3" class="ds-textarea" placeholder="Why is this payment being rejected?"></textarea>
          </span>
          <span v-if="rejectError" class="ds-field-error-text">{{ rejectError }}</span>
        </label>
        <div style="display: flex; gap: var(--ds-space-3); justify-content: flex-end">
          <BaseButton type="button" variant="ghost" :disabled="rejecting" @click="showRejectModal = false">Cancel</BaseButton>
          <BaseButton type="button" variant="danger" class="confirm-reject" :disabled="rejecting" @click="confirmReject">
            {{ rejecting ? 'Rejecting…' : 'Reject order' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>

    <BaseModal v-model="showCancelModal" title="Cancel this order">
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-caption">
          Any still-valid tickets on this order will be voided and can no longer be scanned at
          the door. Tickets already checked in are left untouched.
        </p>
        <label class="ds-field">
          <span class="ds-field-label">Reason for cancellation</span>
          <span class="ds-field-control" :class="{ 'ds-field-control-error': cancelError }">
            <textarea v-model="cancelReason" rows="3" class="ds-textarea" placeholder="Why is this order being cancelled?"></textarea>
          </span>
          <span v-if="cancelError" class="ds-field-error-text">{{ cancelError }}</span>
        </label>
        <div style="display: flex; gap: var(--ds-space-3); justify-content: flex-end">
          <BaseButton type="button" variant="ghost" :disabled="cancelling" @click="showCancelModal = false">Back</BaseButton>
          <BaseButton type="button" variant="danger" class="confirm-cancel" :disabled="cancelling" @click="confirmCancel">
            {{ cancelling ? 'Cancelling…' : 'Cancel order' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </div>
</template>

<style scoped>
/* Resend + Cancel: side by side with a gap; on a phone each takes the full width, stacked, so they never touch. */
.order-actions { display: flex; flex-wrap: wrap; gap: var(--ds-space-3); }
@media (max-width: 640px) {
  .order-actions { flex-direction: column; }
  .order-actions .resend-confirmation,
  .order-actions .cancel-order { width: 100%; justify-content: center; }
}
</style>
