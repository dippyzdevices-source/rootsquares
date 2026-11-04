<script setup lang="ts">
import { ref, onMounted } from 'vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import VippsPaymentPanel from '../../components/ui/VippsPaymentPanel.vue'
import TicketQrCarousel, { type CarouselTicket } from './TicketQrCarousel.vue'
import { fetchMyOrders, confirmPayment, type Order } from '../../services/ordersApi'
import { formatEventDate } from '../../utils/date'
import { formatPrice } from '../../utils/money'
import { useLookup } from '../../composables/useLookup'

const { label: paymentStatusLabel } = useLookup('payment_status')
const loading = ref(true)
const error = ref(false)
const orders = ref<Order[]>([])
const expandedOrderIds = ref<Set<number>>(new Set())
const reportingOrderIds = ref<Set<number>>(new Set())

function badgeTone(order: Order): string {
  return order.payment_status === 'pending_verification' ? 'ds-badge-accent' : 'ds-badge-neutral'
}

function awaitingPayment(order: Order): boolean {
  return order.payment_status === 'pending' || order.payment_status === 'pending_verification'
}

async function reportPayment(order: Order) {
  reportingOrderIds.value = new Set(reportingOrderIds.value).add(order.id)
  try {
    const updated = await confirmPayment(order.order_number, order.customer_email)
    orders.value = orders.value.map((o) => (o.id === updated.id ? updated : o))
  } finally {
    const next = new Set(reportingOrderIds.value)
    next.delete(order.id)
    reportingOrderIds.value = next
  }
}

function toggleOrder(orderId: number) {
  const next = new Set(expandedOrderIds.value)
  if (next.has(orderId)) {
    next.delete(orderId)
  } else {
    next.add(orderId)
  }
  expandedOrderIds.value = next
}

function isExpanded(orderId: number): boolean {
  return expandedOrderIds.value.has(orderId)
}

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

onMounted(async () => {
  try {
    orders.value = (await fetchMyOrders()).items
    if (orders.value.length === 1) {
      expandedOrderIds.value = new Set([orders.value[0].id])
    }
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="ds-scope">
    <div style="max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />My portal</span>
        <h1 class="ds-display ds-display-s">My tickets</h1>
      </div>

      <BaseLoadingState v-if="loading" label="Loading your tickets…" />
      <BaseEmptyState
        v-else-if="error"
        title="Couldn't load your tickets"
        description="Please try again shortly."
      />
      <BaseEmptyState
        v-else-if="orders.length === 0"
        title="No tickets yet"
        description="Tickets you purchase will show up here."
      />
      <div v-else style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <div v-for="order in orders" :key="order.id" class="ds-card" style="padding: 0; overflow: hidden">
          <button
            type="button"
            style="display: flex; width: 100%; align-items: center; justify-content: space-between; gap: var(--ds-space-3); padding: var(--ds-space-4) var(--ds-space-5); border: none; background: none; cursor: pointer; text-align: left; font: inherit; color: inherit"
            :aria-expanded="isExpanded(order.id)"
            @click="toggleOrder(order.id)"
          >
            <div>
              <p class="ds-body" style="font-weight: 600">{{ order.event_title ?? order.order_number }}</p>
              <p class="ds-caption">
                {{ order.order_number }}
                <template v-if="order.event_start_datetime">
                  · {{ formatEventDate(order.event_start_datetime) }}
                </template>
              </p>
            </div>
            <div style="display: flex; flex-shrink: 0; align-items: center; gap: var(--ds-space-3)">
              <span class="ds-caption">{{ ticketCount(order) }} ticket(s)</span>
              <span class="ds-badge" :class="badgeTone(order)">{{ paymentStatusLabel(order.payment_status) }}</span>
              <span
                style="display: inline-block; color: var(--ds-text-faint); transition: transform 220ms var(--ds-ease)"
                :style="isExpanded(order.id) ? 'transform: rotate(180deg)' : ''"
                aria-hidden="true"
              >
                ▾
              </span>
            </div>
          </button>

          <div v-if="isExpanded(order.id)" style="display: flex; flex-direction: column; gap: var(--ds-space-4); padding: var(--ds-space-4) var(--ds-space-5); border-top: 1px solid var(--ds-border-hairline)">
            <p class="ds-meta">Total: {{ formatPrice(order.total_amount) }}</p>
            <TicketQrCarousel v-if="ticketCount(order) > 0" :tickets="carouselTickets(order)" />
            <VippsPaymentPanel
              v-if="awaitingPayment(order)"
              :order-number="order.order_number"
              :total-amount="order.total_amount"
              :payment-status="order.payment_status"
              :reporting="reportingOrderIds.has(order.id)"
              @report="reportPayment(order)"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
