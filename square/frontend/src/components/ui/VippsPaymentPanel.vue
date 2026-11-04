<script setup lang="ts">
import { onMounted, ref } from 'vue'
import BaseButton from './BaseButton.vue'
import VippsQrPicture from './VippsQrPicture.vue'
import { fetchSettings } from '../../services/settingsApi'
import { formatPrice } from '../../utils/money'

const props = defineProps<{
  orderNumber: string
  totalAmount: number
  paymentStatus: string
  reporting?: boolean
}>()

defineEmits<{ report: [] }>()

// The number to pay to is the SQUARE's own, from its settings (rootsquares W6-R38; bca-oslo hardcoded its own number and QR image here).
const vippsNumber = ref<string | null>(null)
const vippsQrImage = ref<string | null>(null)
onMounted(async () => {
  try {
    const settings = await fetchSettings()
    vippsNumber.value = settings.vipps_number ?? null
    vippsQrImage.value = settings.vipps_qr_image_url ?? null
  } catch {
    vippsNumber.value = null
    vippsQrImage.value = null
  }
})

const orderIdCopied = ref(false)

function copyOrderId() {
  navigator.clipboard?.writeText(props.orderNumber)
  orderIdCopied.value = true
  setTimeout(() => (orderIdCopied.value = false), 2000)
}
</script>

<template>
  <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
    <template v-if="paymentStatus === 'pending'">
      <h2 class="ds-subtitle">Pay with Vipps</h2>
      <p v-if="vippsNumber" class="ds-body" style="text-align: center">
        Vipps to <strong>{{ vippsNumber }}</strong>
      </p>
      <p v-else-if="!vippsQrImage" class="ds-body" style="text-align: center">The payment details are not available right now. Please contact us to pay.</p>
      <div v-if="vippsQrImage" style="display: flex; justify-content: center"><VippsQrPicture :src="vippsQrImage" /></div>
      <div class="ds-card ds-card-sunken" style="padding: var(--ds-space-3)">
        <p class="ds-caption">Order ID</p>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-2)">
          <p class="ds-body" style="font-weight: 600">{{ orderNumber }}</p>
          <span class="ds-tooltip">
            <button type="button" class="ds-icon-btn ds-icon-btn-sm" aria-label="Copy order ID" title="Copy order ID" @click="copyOrderId">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
            </button>
            <span class="ds-tooltip-bubble">{{ orderIdCopied ? 'Copied!' : 'Copy order ID' }}</span>
          </span>
        </div>
      </div>
      <p class="ds-meta">
        Pay {{ formatPrice(totalAmount) }} with the Vipps App. Don't forget to mention the order
        ID <strong>{{ orderNumber }}</strong> in the payment message. We'll confirm your payment and issue your
        ticket as soon as possible.
      </p>
      <BaseButton type="button" :disabled="reporting" @click="$emit('report')">
        {{ reporting ? 'Reporting…' : "I've made this payment" }}
      </BaseButton>
    </template>
    <div v-else-if="paymentStatus === 'pending_verification'" class="ds-alert ds-alert-info">
      <div>Thanks — we've noted your payment and will confirm it shortly.</div>
    </div>
  </div>
</template>
