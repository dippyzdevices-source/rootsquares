<script setup lang="ts">
import { formatPrice } from '../../utils/money'

// What a cash payer sees after placing an order: nothing to scan and no "I have paid" button —
// an admin confirms the order once the cash has been received. The wording comes from the admin
// (the event's own cash note, else Settings → Payments); a neutral line is shown when it is empty.
defineProps<{ orderNumber: string; totalAmount: number; note?: string }>()
</script>

<template>
  <div class="ds-card cash-panel" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
    <h2 class="ds-subtitle">Pay with cash</h2>
    <p class="ds-body">
      Amount to pay: <strong>{{ formatPrice(totalAmount) }}</strong>
    </p>
    <div class="ds-card ds-card-sunken" style="padding: var(--ds-space-3)">
      <p class="ds-caption">Order ID</p>
      <p class="ds-body" style="font-weight: 600">{{ orderNumber }}</p>
    </div>
    <p v-if="note" class="ds-body cash-note" style="white-space: pre-line">{{ note }}</p>
    <p v-else class="ds-body cash-note">Pay in cash to the association. Your order is confirmed once we have received the payment.</p>
    <p class="ds-meta">You'll get an email when an admin has confirmed your payment and your tickets are ready.</p>
  </div>
</template>
