<script setup lang="ts">
import { computed, ref } from 'vue'
import BaseButton from './BaseButton.vue'
import { formatPrice } from '../../utils/money'
import type { BankDetails } from '../../services/donationsApi'

// What someone sees after choosing bank transfer for an order: the square's own account details and the order number to write as the
// reference. Same "I've made this payment" step as Vipps-QR; an admin confirms when the money has arrived. An empty detail is not shown.
const props = defineProps<{
  orderNumber: string
  totalAmount: number
  paymentStatus: string
  bank: BankDetails | null | undefined
  reporting?: boolean
}>()

defineEmits<{ report: [] }>()

const rows = computed(() => {
  const b = props.bank
  if (!b) return []
  return [
    { label: 'Account holder', value: b.holder },
    { label: 'Bank', value: b.bank_name },
    { label: 'Account number', value: b.account_number },
    { label: 'IBAN', value: b.iban },
    { label: 'BIC / SWIFT', value: b.bic },
  ].filter((row) => row.value)
})

const copied = ref(false)
function copyOrderId() {
  navigator.clipboard?.writeText(props.orderNumber)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}
</script>

<template>
  <div class="ds-card bank-panel" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
    <template v-if="paymentStatus === 'pending'">
      <h2 class="ds-subtitle">Pay by bank transfer</h2>
      <p class="ds-body">Amount to pay: <strong>{{ formatPrice(totalAmount) }}</strong></p>
      <dl v-if="rows.length" class="bank-details" style="display: grid; grid-template-columns: max-content 1fr; gap: var(--ds-space-1) var(--ds-space-4); margin: 0">
        <template v-for="row in rows" :key="row.label"><dt class="ds-meta">{{ row.label }}</dt><dd style="margin: 0">{{ row.value }}</dd></template>
      </dl>
      <p v-else class="ds-body">The payment details are not available right now. Please contact us to pay.</p>
      <div class="ds-card ds-card-sunken" style="padding: var(--ds-space-3)">
        <p class="ds-caption">Reference (write this in the message)</p>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-2)">
          <p class="ds-body" style="font-weight: 600">{{ orderNumber }}</p>
          <button type="button" class="ds-icon-btn ds-icon-btn-sm" aria-label="Copy reference" :title="copied ? 'Copied!' : 'Copy reference'" @click="copyOrderId">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
          </button>
        </div>
      </div>
      <p v-if="bank?.note" class="ds-body" style="white-space: pre-line">{{ bank.note }}</p>
      <p class="ds-meta">We confirm your payment and issue your tickets once the money has arrived.</p>
      <BaseButton type="button" class="bank-reported" :disabled="reporting" @click="$emit('report')">
        {{ reporting ? 'Reporting…' : "I've made this payment" }}
      </BaseButton>
    </template>
    <div v-else-if="paymentStatus === 'pending_verification'" class="ds-alert ds-alert-info">
      <div>Thanks — we've noted your payment and will confirm it when the money arrives.</div>
    </div>
  </div>
</template>
