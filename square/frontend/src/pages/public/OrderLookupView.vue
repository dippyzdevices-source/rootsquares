<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseBadge from '../../components/ui/BaseBadge.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import CashPaymentPanel from '../../components/ui/CashPaymentPanel.vue'
import BankPaymentPanel from '../../components/ui/BankPaymentPanel.vue'
import VippsPaymentPanel from '../../components/ui/VippsPaymentPanel.vue'
import { lookupOrder, confirmPayment, type Order } from '../../services/ordersApi'
import SquareMark from '../../components/ui/SquareMark.vue'
import { formatPrice } from '../../utils/money'
import { ticketStatusVariant } from '../../utils/ticketStatus'
import { useLookup } from '../../composables/useLookup'

// BaseCard's background follows the site theme, so the icon swaps with it for contrast, same
// as SiteHeader.
const { label: ticketStatusLabel } = useLookup('ticket_status')
const { label: paymentStatusLabel } = useLookup('payment_status')

const orderNumber = ref('')
const email = ref('')
const order = ref<Order | null>(null)
const errorMessage = ref('')
const loading = ref(false)
const reportingPayment = ref(false)

const awaitingPayment = computed(
  () => order.value?.payment_status === 'pending' || order.value?.payment_status === 'pending_verification',
)

async function submit() {
  loading.value = true
  errorMessage.value = ''
  order.value = null
  try {
    order.value = await lookupOrder(orderNumber.value, email.value)
  } catch {
    errorMessage.value = 'Order not found. Check your order number and email and try again.'
  } finally {
    loading.value = false
  }
}

async function reportPayment() {
  if (!order.value) return
  reportingPayment.value = true
  try {
    order.value = await confirmPayment(order.value.order_number, order.value.customer_email)
  } finally {
    reportingPayment.value = false
  }
}

// Deep-linked from the order-received email — see backend/app/orders/emails.py's
// _order_lookup_url() — pre-fills and auto-submits so the customer doesn't retype anything.
const route = useRoute()
onMounted(() => {
  const queryOrderNumber = route.query.order_number
  const queryEmail = route.query.email
  if (typeof queryOrderNumber === 'string' && typeof queryEmail === 'string' && queryOrderNumber && queryEmail) {
    orderNumber.value = queryOrderNumber
    email.value = queryEmail
    submit()
  }
})
</script>

<template>
  <div class="ds-scope">
    <div class="ds-container" style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-6); padding-top: var(--ds-space-8); padding-bottom: var(--ds-space-8)">
      <h1 class="ds-display ds-display-s">Find your order</h1>

      <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Order number</span>
          <span class="ds-field-control"><input v-model="orderNumber" type="text" placeholder="Order number" class="ds-field-input" /></span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Email</span>
          <span class="ds-field-control"><input v-model="email" type="email" placeholder="Email address" class="ds-field-input" /></span>
        </label>
        <BaseButton type="button" variant="primary" class="lookup-order" :disabled="loading" @click="submit">
          {{ loading ? 'Looking up…' : 'Find my order' }}
        </BaseButton>
      </div>

      <div v-if="errorMessage" class="ds-alert ds-alert-danger"><div>{{ errorMessage }}</div></div>

      <div v-if="order" class="ds-row" :class="awaitingPayment ? 'ds-row--sidebar' : ''">
        <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <div style="display: flex; align-items: center; gap: var(--ds-space-2)">
            <SquareMark :size="20" />
            <p class="ds-meta">Order {{ order.order_number }}</p>
          </div>
          <p class="ds-body">
            Payment status:
            <span class="ds-badge" :class="order.payment_status === 'pending_verification' ? 'ds-badge-accent' : 'ds-badge-neutral'">
              {{ paymentStatusLabel(order.payment_status) }}
            </span>
          </p>
          <p class="ds-title">{{ formatPrice(order.total_amount) }}</p>

          <div v-for="item in order.items" :key="item.id" style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
            <p class="ds-meta">{{ item.quantity }} × {{ item.ticket_type_name }}</p>
            <div v-if="item.tickets.length" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: var(--ds-space-3)">
              <div v-for="ticket in item.tickets" :key="ticket.id" style="text-align: center">
                <div style="position: relative; margin: 0 auto; width: 110px">
                  <img
                    :src="ticket.qr_code_data_url"
                    :alt="ticket.ticket_code"
                    style="width: 110px"
                    :style="ticket.status === 'used' ? 'opacity: 0.3' : ''"
                  />
                  <div v-if="ticket.status === 'used'" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center">
                    <span style="display: flex; height: 36px; width: 36px; align-items: center; justify-content: center; border-radius: 999px; background: var(--ds-status-success); color: white; font-size: 18px">✓</span>
                  </div>
                </div>
                <BaseBadge :variant="ticketStatusVariant(ticket.status)" style="margin-top: var(--ds-space-1)">
                  {{ ticketStatusLabel(ticket.status) }}
                </BaseBadge>
              </div>
            </div>
          </div>
        </div>

        <CashPaymentPanel
          v-if="awaitingPayment && order.payment_method === 'cash'"
          :order-number="order.order_number"
          :total-amount="order.total_amount"
          :note="order.cash_note"
        />
        <BankPaymentPanel
          v-else-if="awaitingPayment && order.payment_method === 'bank_transfer'"
          :order-number="order.order_number"
          :total-amount="order.total_amount"
          :payment-status="order.payment_status"
          :bank="order.bank"
          :reporting="reportingPayment"
          @report="reportPayment"
        />
        <VippsPaymentPanel
          v-else-if="awaitingPayment"
          :order-number="order.order_number"
          :total-amount="order.total_amount"
          :payment-status="order.payment_status"
          :reporting="reportingPayment"
          @report="reportPayment"
        />
      </div>
    </div>
  </div>
</template>
