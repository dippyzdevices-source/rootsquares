<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import KeyValue from '@/components/ui/KeyValue.vue'
import { platform, type BillingOrder } from '@/services/platform'
import { usd } from '@rootsquares/ui/mock/pricing'
import { errorText } from '@/features/platform/errorText'

// The TEST checkout (W10-R42): what the fake billing provider sends the owner to. It shows what is bought and lets the owner pay or cancel; no money moves and no
// card is asked for. With Stripe the owner goes to Stripe's own page instead and never sees this one.
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const order = ref<BillingOrder | null>(null)
const error = ref('')
const busy = ref(false)
const orderId = computed(() => String(route.query.order ?? ''))
const what = computed(() => {
  const o = order.value
  if (!o) return ''
  if (o.kind === 'first') return t('portal.checkout.first', { package: t(`marketing.pricing.launch.${o.launch_package}.name`) })
  if (o.kind === 'event_pass') return t('portal.checkout.eventPass')
  if (o.kind === 'event_upgrade') return t('portal.checkout.eventUpgrade', { package: t(`marketing.pricing.launch.${o.launch_package}.name`) })
  if (o.kind === 'upgrade') return t('portal.checkout.upgrade', { package: t(`marketing.pricing.launch.${o.launch_package}.name`) })
  return t('portal.checkout.running', { plan: t(`marketing.pricing.running.${o.running_plan}.name`), interval: t(o.interval === 'year' ? 'portal.checkout.year' : 'portal.checkout.month') })
})

onMounted(async () => {
  try { order.value = await platform.getOrder(orderId.value) } catch (e) { error.value = errorText(t, e) }
})

async function finish(outcome: 'paid' | 'cancelled') {
  if (!order.value) return
  busy.value = true
  error.value = ''
  try {
    const done = await platform.fakeConfirm(order.value.id, outcome)
    await router.push({ path: `/squares/${done.square_id}/billing`, query: { [done.status === 'paid' ? 'paid' : 'cancelled']: '1' } })
  } catch (e) { error.value = errorText(t, e) } finally { busy.value = false }
}
</script>

<template>
  <div class="bw-checkout" data-testid="test-checkout" style="max-width: 520px; margin: 24px auto; padding: 0 16px; display: grid; gap: 14px">
    <h2 class="bs-h2" style="font-size: 28px; margin: 0">{{ t('portal.checkout.title') }}</h2>
    <AppAlert tone="info" :title="t('portal.checkout.testTitle')">{{ t('portal.checkout.testBody') }}</AppAlert>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <template v-if="order">
      <KeyValue :rows="[[t('portal.checkout.item'), what], [t('portal.checkout.amount'), usd(order.amount_minor)], [t('portal.checkout.status'), t(`portal.checkout.states.${order.status}`)]]" />
      <div v-if="order.status === 'pending'" class="bs-row" style="gap: 10px; flex-wrap: wrap">
        <AppButton icon="card" :loading="busy" @click="finish('paid')">{{ t('portal.checkout.pay', { amount: usd(order.amount_minor) }) }}</AppButton>
        <AppButton icon="x" variant="secondary" :disabled="busy" @click="finish('cancelled')">{{ t('portal.checkout.cancel') }}</AppButton>
      </div>
      <AppButton v-else icon="chevron-left" variant="secondary" :to="`/squares/${order.square_id}/billing`">{{ t('portal.checkout.back') }}</AppButton>
    </template>
  </div>
</template>
