<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { checkVippsReturn } from '../../services/vippsAppApi'

// Where Vipps sends a donor back to. Like VippsReturnView: the page only asks the server to re-check the payment with Vipps.
const route = useRoute()
const loading = ref(true)
const status = ref<string | null>(null)
const failed = ref(false)

onMounted(async () => {
  const reference = String(route.query.ref ?? '')
  if (!reference) {
    failed.value = true
    loading.value = false
    return
  }
  try {
    status.value = (await checkVippsReturn(reference)).status
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
      <BaseLoadingState v-if="loading" label="Checking your payment with Vipps…" />
      <div v-else-if="failed" class="ds-alert ds-alert-danger"><div>We couldn't check your payment right now. If money left your account, don't pay again: you will get a receipt by e-mail once Vipps confirms it.</div></div>
      <div v-else-if="status === 'paid'" class="ds-card donate-paid" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <h1 class="ds-display ds-display-s">Thank you for your gift!</h1>
        <p class="ds-body">Your payment is confirmed. A receipt is on its way to your e-mail.</p>
        <div><BaseButton type="button" variant="secondary" to="/">Back to the home page</BaseButton></div>
      </div>
      <div v-else-if="status === 'initiated'" class="ds-alert ds-alert-info"><div>Vipps has not confirmed your payment yet. If you finished it in the Vipps app, your receipt is e-mailed as soon as it is confirmed.</div></div>
      <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <h1 class="ds-display ds-display-s">The payment wasn't completed</h1>
        <p class="ds-body">No money was taken. You can try again.</p>
        <div><BaseButton type="button" variant="secondary" to="/donate">Back to donate</BaseButton></div>
      </div>
    </div>
  </div>
</template>
