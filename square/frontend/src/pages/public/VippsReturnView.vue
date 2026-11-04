<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { checkVippsReturn } from '../../services/vippsAppApi'

// Where Vipps sends a ticket buyer back to (guest or signed in). The page only asks the backend
// to re-check the payment with Vipps — the outcome shown comes from Vipps, never from the URL.
const route = useRoute()
const loading = ref(true)
const status = ref<string | null>(null)
const orderNumber = ref<string | null>(null)
const failed = ref(false)
const isMembership = route.query.kind === 'membership'
const isDonation = route.query.kind === 'donation'
const cancelled = route.query.cancelled === '1' // the customer pressed back on the card page
const provider = ref<string | null>(null)
const isCard = () => provider.value === 'stripe'

onMounted(async () => {
  const reference = String(route.query.ref ?? '')
  if (!reference) {
    failed.value = true
    loading.value = false
    return
  }
  try {
    const result = await checkVippsReturn(reference, cancelled)
    status.value = result.status
    provider.value = result.provider ?? null
    orderNumber.value = result.order_number
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="ds-scope">
    <div class="ds-container" style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-5); padding-top: var(--ds-space-8); padding-bottom: var(--ds-space-8)">
      <BaseLoadingState v-if="loading" label="Checking your payment…" />

      <div v-else-if="failed" class="ds-alert ds-alert-danger">
        <div>We couldn't check your payment right now. If money left your account, don't pay again — {{ isMembership ? 'your membership activates once the payment is confirmed' : isDonation ? 'your donation is recorded once the payment is confirmed' : 'your tickets will be emailed once the payment is confirmed' }}, or contact us.</div>
      </div>

      <div v-else-if="status === 'paid'" class="ds-card vipps-return-paid" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <h1 class="ds-display ds-display-s">Payment received — thank you!</h1>
        <p v-if="isDonation" class="ds-body">Thank you for your donation!</p>
        <p v-else-if="isMembership" class="ds-body">Your membership is now active. Welcome to {{ squareProfile.name }}!</p>
        <p v-else-if="orderNumber" class="ds-body">Order {{ orderNumber }} is confirmed. We've emailed your QR-coded tickets.</p>
        <p v-else class="ds-body">Your payment has been confirmed.</p>
        <div style="display: flex; gap: var(--ds-space-3); flex-wrap: wrap">
          <template v-if="isDonation"><BaseButton type="button" variant="secondary" to="/events">Back to events</BaseButton></template>
          <template v-else-if="isMembership"><BaseButton type="button" variant="secondary" to="/member">My dashboard</BaseButton></template>
          <template v-else>
            <BaseButton type="button" variant="secondary" to="/orders/lookup">Find my order</BaseButton>
            <BaseButton type="button" variant="ghost" to="/member/tickets">My tickets</BaseButton>
          </template>
        </div>
      </div>

      <div v-else-if="status === 'initiated'" class="ds-alert ds-alert-info vipps-return-waiting">
        <div>{{ isCard() ? 'The card payment' : 'Vipps' }} hasn't confirmed your payment yet. If you completed it{{ isCard() ? '' : ' in the Vipps App' }}, {{ isMembership ? 'your membership activates' : isDonation ? 'your donation is recorded' : `your tickets will be emailed (order ${orderNumber})` }} as soon as it is confirmed.</div>
      </div>

      <div v-else class="ds-card vipps-return-failed" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <h1 class="ds-display ds-display-s">{{ cancelled ? 'You cancelled the payment' : "The payment wasn't completed" }}</h1>
        <p class="ds-body">No money was taken. {{ isMembership ? 'You can try again from the membership page.' : isDonation ? 'You can try again from the event page.' : 'You can place the order again from the event page.' }}</p>
        <div><BaseButton type="button" variant="secondary" :to="isMembership ? '/membership' : '/events'">{{ isMembership ? 'Back to membership' : 'Back to events' }}</BaseButton></div>
      </div>
    </div>
  </div>
</template>
