<script setup lang="ts">
// A parent paying for their child's membership — e.g. one a volunteer saved with "pay later" at the
// Membership Drive. Lists each child whose membership is waiting for its first payment and offers the
// same payment methods as the member's own membership. Renders nothing when there is no such child.
import { onMounted, ref } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import { useToast } from '../composables/useToast'
import {
  fetchChildrenAwaitingPayment,
  startPeriodPayment,
  type ChildAwaitingPayment,
} from '../services/membershipPaymentsApi'
import { humanize } from '../utils/formatEnum'
import { formatPrice } from '../utils/money'
import { useVippsNumber, useVippsQrImage } from '../composables/useVippsNumber'
import VippsQrPicture from './ui/VippsQrPicture.vue'

type Method = 'vipps_qr' | 'vipps_app' | 'stripe' | 'cash'

const toast = useToast()
const vippsNumber = useVippsNumber()
const vippsQrImage = useVippsQrImage()

const children = ref<ChildAwaitingPayment[]>([])
const vippsApp = ref({ enabled: false, surcharge_percent: 0 })
const stripeCard = ref({ enabled: false, surcharge_percent: 0 })
const cash = ref({ enabled: false, note: '' })
const method = ref<Record<number, Method>>({})
const paying = ref<number | null>(null)

async function load() {
  try {
    const res = await fetchChildrenAwaitingPayment()
    children.value = res.items
    vippsApp.value = res.vipps_app ?? vippsApp.value
    stripeCard.value = res.stripe ?? stripeCard.value
    cash.value = res.cash ?? cash.value
  } catch {
    children.value = [] // secondary to the rest of the dashboard — stay silent
  }
}

function chosen(child: ChildAwaitingPayment): Method {
  return method.value[child.member_id] ?? 'vipps_qr'
}

const fee = (child: ChildAwaitingPayment) =>
  Math.floor((child.period.amount * (chosen(child) === 'stripe' ? stripeCard.value.surcharge_percent : vippsApp.value.surcharge_percent) + 50) / 100)

async function pay(child: ChildAwaitingPayment, provider: Method) {
  paying.value = child.member_id
  try {
    const res = await startPeriodPayment({ periodIds: [child.period.id], provider })
    if (provider === 'vipps_app' || provider === 'stripe') {
      if (!res.redirect_url) throw new Error('No redirect URL')
      window.location.href = res.redirect_url
      return
    }
    toast.success(
      provider === 'cash'
        ? "Thanks — an admin will confirm the payment once the cash is received."
        : "Thanks — we've noted the payment and will confirm it shortly.",
    )
    await load()
  } catch {
    toast.error('Could not register the payment')
  } finally {
    paying.value = null
  }
}

onMounted(load)
</script>

<template>
  <section v-if="children.length > 0" class="child-payments" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
    <h2 class="ds-title">Children's membership</h2>
    <div
      v-for="child in children"
      :key="child.member_id"
      class="ds-card child-payment"
      style="display: flex; flex-direction: column; gap: var(--ds-space-3)"
    >
      <div style="display: flex; justify-content: space-between; align-items: baseline; gap: var(--ds-space-3); flex-wrap: wrap">
        <p class="ds-body" style="font-weight: 600; margin: 0">{{ child.name }} · {{ humanize(child.membership_type) }}</p>
        <span class="ds-meta">{{ child.period.label }} · {{ formatPrice(child.period.amount) }}</span>
      </div>

      <div v-if="child.period.payment_pending" class="ds-alert ds-alert-info awaiting-confirmation">
        <div>Payment reported — awaiting confirmation. The membership activates as soon as it is confirmed.</div>
      </div>

      <template v-else>
        <p class="ds-meta" style="margin: 0">Pay to activate {{ child.name }}'s membership.</p>
        <div v-if="vippsApp.enabled || stripeCard.enabled || cash.enabled" class="child-methods" role="radiogroup" aria-label="Payment method" style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
          <label class="ds-tag" :class="{ 'ds-tag-selected': chosen(child) === 'vipps_qr' }" style="cursor: pointer">
            <input v-model="method[child.member_id]" type="radio" :name="`child-pay-${child.member_id}`" value="vipps_qr" style="position: absolute; opacity: 0; pointer-events: none" />
            Vipps-QR
          </label>
          <label v-if="vippsApp.enabled" class="ds-tag" :class="{ 'ds-tag-selected': chosen(child) === 'vipps_app' }" style="cursor: pointer">
            <input v-model="method[child.member_id]" type="radio" :name="`child-pay-${child.member_id}`" value="vipps_app" style="position: absolute; opacity: 0; pointer-events: none" />
            Vipps-App
          </label>
          <label v-if="stripeCard.enabled" class="ds-tag" :class="{ 'ds-tag-selected': chosen(child) === 'stripe' }" style="cursor: pointer">
            <input v-model="method[child.member_id]" type="radio" :name="`child-pay-${child.member_id}`" value="stripe" style="position: absolute; opacity: 0; pointer-events: none" />
            Card
          </label>
          <label v-if="cash.enabled" class="ds-tag" :class="{ 'ds-tag-selected': chosen(child) === 'cash' }" style="cursor: pointer">
            <input v-model="method[child.member_id]" type="radio" :name="`child-pay-${child.member_id}`" value="cash" style="position: absolute; opacity: 0; pointer-events: none" />
            Cash
          </label>
        </div>

        <div v-if="chosen(child) === 'vipps_app'" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <p class="ds-meta" style="margin: 0">
            {{ formatPrice(child.period.amount) }} + {{ formatPrice(fee(child)) }} convenience fee
            = <strong>{{ formatPrice(child.period.amount + fee(child)) }}</strong>
          </p>
          <BaseButton type="button" :disabled="paying === child.member_id" @click="pay(child, 'vipps_app')">
            {{ paying === child.member_id ? 'Opening Vipps…' : `Pay ${formatPrice(child.period.amount + fee(child))} with Vipps` }}
          </BaseButton>
        </div>
        <div v-else-if="chosen(child) === 'stripe'" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <p v-if="fee(child) > 0" class="ds-meta" style="margin: 0">
            {{ formatPrice(child.period.amount) }} + {{ formatPrice(fee(child)) }} convenience fee
            = <strong>{{ formatPrice(child.period.amount + fee(child)) }}</strong>
          </p>
          <BaseButton type="button" :disabled="paying === child.member_id" @click="pay(child, 'stripe')">
            {{ paying === child.member_id ? 'Opening the card page…' : `Pay ${formatPrice(child.period.amount + fee(child))} by card` }}
          </BaseButton>
        </div>
        <div v-else-if="chosen(child) === 'cash'" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <p class="ds-meta cash-note" style="margin: 0; white-space: pre-line">{{ cash.note || 'Pay the amount in cash to the association. The membership is confirmed once an admin has received it.' }}</p>
          <BaseButton type="button" :disabled="paying === child.member_id" @click="pay(child, 'cash')">
            {{ paying === child.member_id ? 'Sending…' : `I'll pay ${formatPrice(child.period.amount)} in cash` }}
          </BaseButton>
        </div>
        <div v-else style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <p v-if="vippsNumber" class="ds-body" style="text-align: center; margin: 0">Vipps to <strong>{{ vippsNumber }}</strong></p>
          <div style="display: flex; justify-content: center"><VippsQrPicture :src="vippsQrImage" /></div>
          <p class="ds-meta" style="margin: 0">
            Pay {{ formatPrice(child.period.amount) }} and mention {{ child.name }}'s name in the payment message. Then tap the button below —
            we'll confirm the payment as soon as possible.
          </p>
          <BaseButton type="button" :disabled="paying === child.member_id" @click="pay(child, 'vipps_qr')">
            {{ paying === child.member_id ? 'Reporting…' : "I've made this payment" }}
          </BaseButton>
        </div>
      </template>
    </div>
  </section>
</template>

<style scoped>
/* Long labels ("Pay 105.00 kr with Vipps") must wrap on a phone instead of spilling out of the card. */
.child-payments :deep(.ds-btn) { white-space: normal; text-align: center; line-height: 1.25; max-width: 100%; width: 100%; height: auto; min-height: 48px; }
</style>
