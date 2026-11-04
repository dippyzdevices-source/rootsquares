<script setup lang="ts">
import { moduleEnabled } from '../../services/modules'
import { ref, onMounted } from 'vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchMyOrders, type Order } from '../../services/ordersApi'
import {
  fetchMyMembershipPayments,
  type MembershipPaymentHistoryItem,
} from '../../services/membershipPaymentsApi'
import { formatEventDate } from '../../utils/date'
import { formatPrice } from '../../utils/money'
import { useLookup } from '../../composables/useLookup'

// Mirrors AdminOrdersListView.vue/AdminPaymentsView.vue's own statusTone() so a given
// payment status always maps to the same badge color everywhere in the app.
const { label: paymentStatusLabel } = useLookup('payment_status')
function statusTone(value: string): string {
  if (value === 'paid') return 'ds-badge-success'
  if (value === 'failed' || value === 'cancelled' || value === 'rejected') return 'ds-badge-danger'
  if (value === 'refunded') return 'ds-badge-info'
  if (value === 'pending_verification' || value === 'pending') return 'ds-badge-accent'
  return 'ds-badge-neutral'
}

const loading = ref(true)
const error = ref(false)
const orders = ref<Order[]>([])
const ticketsOn = moduleEnabled('tickets') // W8-R29
const membershipsOn = moduleEnabled('memberships') // W8-R19
const membershipPayments = ref<MembershipPaymentHistoryItem[]>([])
const membershipPaymentsError = ref(false)

onMounted(async () => {
  try {
    if (ticketsOn) orders.value = (await fetchMyOrders()).items
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }

  try {
    if (membershipsOn) membershipPayments.value = await fetchMyMembershipPayments()
  } catch {
    membershipPaymentsError.value = true
  }
})
</script>

<template>
  <div class="ds-scope">
    <div style="max-width: 780px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--ds-space-7)">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />My portal</span>
        <h1 class="ds-display ds-display-s">Payments</h1>
      </div>

      <section v-if="ticketsOn" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <BaseLoadingState v-if="loading" label="Loading your payment history…" />
        <BaseEmptyState
          v-else-if="error"
          title="Couldn't load your payment history"
          description="Please try again shortly."
        />
        <BaseEmptyState
          v-else-if="orders.length === 0"
          title="No payments yet"
          description="Payments you make will show up here."
        />
        <div v-else class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table">
              <caption>Ticket receipts</caption>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Date</th>
                  <th data-align="right">Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="order in orders" :key="order.id">
                  <td data-emphasis>
                    {{ order.event_title ?? order.order_number }}
                    <div class="ds-caption">{{ order.order_number }}</div>
                  </td>
                  <td>{{ formatEventDate(order.created_at) }}</td>
                  <td data-align="right">{{ formatPrice(order.total_amount) }}</td>
                  <td><span class="ds-badge" :class="statusTone(order.payment_status)">{{ paymentStatusLabel(order.payment_status) }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section v-if="membershipsOn && !loading" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <h2 class="ds-title">Membership Payments</h2>
        <div v-if="membershipPaymentsError" class="ds-alert ds-alert-danger">
          <div>Couldn't load your membership payments. Please try again shortly.</div>
        </div>
        <BaseEmptyState
          v-else-if="membershipPayments.length === 0"
          title="No membership payments yet"
          description="Membership payments you make will show up here."
        />
        <div v-else class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table">
              <caption>Membership receipts</caption>
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Date</th>
                  <th data-align="right">Amount</th>
                  <th>Status</th>
                  <th>Periods</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="payment in membershipPayments" :key="payment.id">
                  <td data-emphasis>{{ payment.payment_reference }}</td>
                  <td>{{ formatEventDate(payment.created_at) }}</td>
                  <td data-align="right">{{ formatPrice(payment.amount) }}</td>
                  <td><span class="ds-badge" :class="statusTone(payment.status)">{{ paymentStatusLabel(payment.status) }}</span></td>
                  <td class="ds-meta">{{ payment.allocations.map((a) => a.label).join(', ') }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
