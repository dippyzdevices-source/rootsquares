<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import PlanCards from './PlanCards.vue'
import TaxLine from '@/components/ui/TaxLine.vue'
import EventPassCard from './EventPassCard.vue'
import VoucherField from './VoucherField.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { ApiError, platform, type CheckoutInput, type LaunchPackageId, type PlanPrice } from '@/services/platform'
import { usd } from '@rootsquares/ui/mock/pricing'
import { savedReferral } from '@/services/referral'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/features/platform/errorText'
import { useSquare } from './squareContext'

// The square's plan (W10-R41, W10-R42, docs/plans/pricing-strategy.md): the launch package and the running plan; the owner can switch between Live and Keep (asleep), move up a
// launch package (pays the difference) and pay for a running period. Payment goes through the billing provider: the test checkout page now, Stripe later. The plan
// changes only when the payment is confirmed. Prices come from the platform (data).
const { t } = useI18n()
const route = useRoute()
const { push } = useToast()
const { date } = useFormat()
const { sq, set } = useSquare()
const busy = ref(false)
const error = ref('')
const dialog = ref<'' | 'downgrade' | 'upgrade'>('') // the confirm box of a plan change (W18-R34)
const declined = ref(false) // the last change failed on the card: the page offers the card page
const needsPayment = ref(false)
const prices = ref<PlanPrice[]>([])

const rows = computed<[string, string][]>(() => {
  const x = sq.value!
  const out: [string, string][] = [
    [t('portal.plan.package'), x.launch_package === 'event' ? t('marketing.pricing.running.event.name') : t(`marketing.pricing.launch.${x.launch_package}.name`)],
    [t('portal.plan.running'), t(`marketing.pricing.running.${x.running_plan}.name`)],
  ]
  if (x.paid_until) out.push([t('portal.plan.paidUntil'), date(x.paid_until, { day: 'numeric', month: 'short', year: 'numeric' })])
  return out
})
const trialEnded = computed(() => !!sq.value?.paid_until && new Date(sq.value.paid_until) <= new Date())
// The package of the first payment: the one the square started with or a higher one, paid in full (W12-R16).
const LADDER: LaunchPackageId[] = ['roots', 'square', 'grove']
const firstPackages = computed(() => LADDER.slice(Math.max(0, LADDER.indexOf(sq.value?.launch_package as LaunchPackageId))))
const chosenPkg = ref<LaunchPackageId | ''>('')
const firstPkg = computed<LaunchPackageId>({ get: () => chosenPkg.value || firstPackages.value[0] || 'roots', set: (v) => { chosenPkg.value = v } })
const firstAmount = (iv: 'month' | 'year') => {
  const price = (key: string) => prices.value.find((p) => p.key === key)?.amount_minor ?? 0
  return price(`launch.${firstPkg.value}`) + price(`running.live.${iv}`)
}
const returnedPaid = computed(() => route.query.paid === '1')
// Coming back from the checkout page (?paid=1) proves nothing: the plan changes only when the payment provider's message has been received and the order is paid
// (W25-R26). So the page asks for the newest order until it is paid, and only then says "Payment received"; if it stays pending it says so instead.
// While it is pending the backend is also asked to look at the payment provider itself (W25-R27), so a webhook that never came cannot leave a paid order pending.
const payState = ref<'checking' | 'paid' | 'waiting' | ''>('')
const justPaid = computed(() => payState.value === 'paid')
async function confirmPayment() {
  if (!sq.value) return
  payState.value = 'checking'
  for (let i = 0; i < 12; i++) {
    try {
      const orders = await platform.listOrders(sq.value.id)
      let newest = [...orders].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
      if (newest?.status === 'pending') newest = await platform.confirmOrder(sq.value.id, newest.id)
      if (newest?.status === 'paid') {
        payState.value = 'paid'
        try { set(await platform.getSquare(sq.value.id)) } catch { /* the page still shows the old plan until reload */ }
        return
      }
      if (newest && newest.status !== 'pending') break // cancelled or failed: the cancelled message or the order list says what happened
    } catch { /* try again */ }
    await new Promise((r) => window.setTimeout(r, 2500))
  }
  payState.value = 'waiting'
}
const justCancelled = computed(() => route.query.cancelled === '1')

async function loadAll() {
  if (!sq.value) return
  try { prices.value = await platform.getPrices() } catch { /* the buttons then show no price */ }
}
onMounted(async () => {
  await loadAll()
  if (returnedPaid.value) await confirmPayment()
})

// While the project wakes (a minute or two at the provider) the page asks again every few seconds until the square is awake or the wake failed.
let poll = 0
function stopPoll() { window.clearInterval(poll); poll = 0 }
watch(() => sq.value?.sleep_state, (state) => {
  if (state === 'waking' && !poll) {
    poll = window.setInterval(async () => {
      if (!sq.value) return
      try { set(await platform.getSquare(sq.value.id)) } catch { /* try again next time */ }
    }, 4000)
  } else if (state !== 'waking') stopPoll()
}, { immediate: true })
onBeforeUnmount(stopPoll)

async function change(plan: 'keep' | 'live') {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  needsPayment.value = false
  try {
    set(await platform.setRunningPlan(sq.value.id, plan))
    push(t(plan === 'keep' ? 'portal.plan.slept' : sq.value.sleep_state === 'waking' ? 'portal.plan.wakingToast' : 'portal.plan.woke'), 'success')
  } catch (e) {
    if (e instanceof ApiError && e.code === 'payment_required') needsPayment.value = true
    else error.value = errorText(t, e)
  } finally { busy.value = false }
}

// Live and Keep (W18-R34, docs/plans/plan-changes-plan.md): a downgrade starts at the next renewal, an upgrade at once, a waiting downgrade can be cancelled. Every stage says
// what happens, when, and what it costs; nothing here is a guess except the amount of an upgrade, which is worked out from the days left and said to be "about".
const endDate = computed(() => (sq.value?.paid_until ? date(sq.value.paid_until, { day: 'numeric', month: 'short', year: 'numeric' }) : ''))
const renewing = computed(() => sq.value?.subscription === 'renewing')
const iv = computed<'month' | 'year'>(() => (sq.value?.billing_interval === 'year' ? 'year' : 'month'))
const priceOf = (plan: 'live' | 'keep') => prices.value.find((p) => p.key === `running.${plan}.${iv.value}`)?.amount_minor ?? 0
const priceText = (plan: 'live' | 'keep') => `${usd(priceOf(plan))} ${t(iv.value === 'year' ? 'marketing.pricing.perYear' : 'marketing.pricing.perMonth')}`
const upgradeEstimate = computed(() => {
  const x = sq.value
  if (!x?.paid_until) return 0
  const days = iv.value === 'year' ? 365 : 30
  const left = Math.max(0, Math.min(days, (new Date(x.paid_until).getTime() - Date.now()) / 86_400_000))
  return Math.max(0, Math.round(((priceOf('live') - priceOf('keep')) * left) / days))
})
function askChange(plan: 'keep' | 'live') {
  if (plan === 'keep') dialog.value = 'downgrade'
  else if (sq.value?.pending_plan === 'keep') void changePlan('live') // cancelling a waiting downgrade needs no question
  else dialog.value = 'upgrade'
}
async function changePlan(plan: 'keep' | 'live') {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  declined.value = false
  needsPayment.value = false
  const waiting = sq.value.pending_plan === 'keep'
  try {
    set(await platform.changePlan(sq.value.id, plan))
    if (plan === 'keep') push(t('portal.plan.scheduledToast', { date: endDate.value }), 'success')
    else if (waiting) push(t(renewing.value ? 'portal.plan.stayedToastRenewing' : 'portal.plan.stayedToast', { date: endDate.value }), 'success')
    else push(t(sq.value.sleep_state === 'waking' ? 'portal.plan.wakingToast' : renewing.value ? 'portal.plan.upgradedToast' : 'portal.plan.woke'), 'success')
  } catch (e) {
    if (e instanceof ApiError && e.code === 'payment_required') needsPayment.value = true
    else error.value = errorText(t, e)
    declined.value = e instanceof ApiError && (e.code === 'plan_change_declined' || e.code === 'payment_failed')
  } finally { busy.value = false; dialog.value = '' }
}

// The owner of an Event pass says the reports are saved (W11, ADR 044): a plain yes, nothing about their content.
async function confirmExport() {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  try {
    set(await platform.confirmEventPassExport(sq.value.id))
    push(t('portal.eventPass.exportToast'), 'success')
  } catch (e) { error.value = errorText(t, e) } finally { busy.value = false }
}

async function openCard() {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  try { window.location.assign((await platform.billingPortal(sq.value.id)).url) } catch (e) { error.value = errorText(t, e); busy.value = false }
}

async function renewal(resume: boolean) {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  try {
    set(await (resume ? platform.resumeRenewal(sq.value.id) : platform.cancelRenewal(sq.value.id)))
    push(t(resume ? 'portal.renewal.resumed' : 'portal.renewal.cancelled'), 'success')
  } catch (e) { error.value = errorText(t, e) } finally { busy.value = false }
}

const voucher = ref(savedReferral())
watch(() => sq.value?.voucher_code, (code) => { if (code && !voucher.value) voucher.value = code }, { immediate: true }) // the code given at creation fills the box (W14-R30)
async function pay(input: CheckoutInput) {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  try {
    // a code lowers a launch package or an Event pass once, never a running period on its own
    const code = voucher.value.trim()
    const { url } = await platform.startCheckout(sq.value.id, code && input.kind !== 'running' ? { ...input, voucher_code: code } : input)
    window.location.assign(url) // the test checkout page now, Stripe's page later
  } catch (e) { error.value = errorText(t, e); busy.value = false }
}
</script>

<template>
  <section v-if="sq" style="display: grid; gap: 12px" data-testid="plan-card">
    <h3 class="bs-h2" style="font-size: 20px; margin: 0">{{ t('portal.plan.title') }}</h3>
    <AppAlert v-if="payState === 'checking'" tone="info" :title="t('portal.plan.confirmingTitle')">{{ t('portal.plan.confirmingBody') }}</AppAlert>
    <AppAlert v-else-if="justPaid" tone="success" :title="t('portal.plan.paidTitle')">{{ t('portal.plan.paidBody') }}</AppAlert>
    <AppAlert v-else-if="payState === 'waiting'" tone="warning" :title="t('portal.plan.unconfirmedTitle')" data-testid="payment-unconfirmed">{{ t('portal.plan.unconfirmedBody') }}</AppAlert>
    <AppAlert v-else-if="justCancelled" tone="info">{{ t('portal.plan.cancelled') }}</AppAlert>
    <!-- The current plan in a card: Brass eyebrow labels (the design system's contrast colour for small labels), the values large -->
    <div class="pc-now" data-testid="current-plan">
      <div v-for="[label, value] in rows" :key="label" class="pc-now__item"><span class="rs-eyebrow">{{ label }}</span><b>{{ value }}</b></div>
      <p class="bs-mute pc-now__text">{{ t(`portal.plan.${sq.running_plan}`) }}</p>
    </div>
    <AppAlert v-if="sq.sleep_state === 'waking'" tone="info" :title="t('portal.plan.wakingTitle')">{{ t('portal.plan.wakingBody') }}</AppAlert>
    <AppAlert v-else-if="sq.sleep_state === 'failed'" tone="danger" :title="t('portal.plan.wakeFailedTitle')">{{ t('portal.plan.wakeFailedBody') }}</AppAlert>
    <AppAlert v-if="sq.pending_plan === 'keep'" tone="info" :title="t('portal.plan.pendingTitle', { date: endDate })" data-testid="pending-plan">
      {{ t('portal.plan.pendingBody', { price: priceText('keep') }) }}
      <AppButton icon="card" variant="secondary" :disabled="busy" style="min-height: 44px; margin-top: 10px" @click="changePlan('live')">{{ t('portal.plan.stayLive') }}</AppButton>
    </AppAlert>
    <AppAlert v-if="error" tone="danger" :title="declined ? t('portal.plan.declinedTitle') : undefined">
      {{ error }}
      <AppButton v-if="declined && sq.can_manage_billing" icon="card" :disabled="busy" style="min-height: 44px; margin-top: 10px" @click="openCard">{{ t('portal.plan.updateCard') }}</AppButton>
    </AppAlert>
    <AppAlert v-if="needsPayment" tone="warning" :title="t('portal.plan.needsPaymentTitle')">{{ t('portal.plan.needsPaymentBody') }}</AppAlert>

    <AppAlert v-if="sq.payment_failed" tone="danger" :title="t('portal.failed.title')" data-testid="payment-failed">
      {{ t('portal.failed.body', { date: sq.grace_ends ? date(sq.grace_ends, { day: 'numeric', month: 'short', year: 'numeric' }) : '' }) }}
      <AppButton v-if="sq.can_manage_billing" icon="card" :disabled="busy" style="min-height: 44px; margin-top: 10px" @click="openCard">{{ t('portal.failed.update') }}</AppButton>
    </AppAlert>
    <AppAlert v-if="sq.subscription" :tone="sq.subscription === 'ending' ? 'warning' : 'info'" :title="t(sq.subscription === 'ending' ? 'portal.renewal.endingTitle' : 'portal.renewal.title')" data-testid="renewal">
      {{ t(sq.subscription === 'ending' ? 'portal.renewal.endingBody' : 'portal.renewal.body', { date: sq.paid_until ? date(sq.paid_until, { day: 'numeric', month: 'short', year: 'numeric' }) : '' }) }}
      <AppButton icon="refresh" variant="secondary" :disabled="busy" style="min-height: 44px; margin-top: 10px" @click="renewal(sq.subscription === 'ending')">{{ t(sq.subscription === 'ending' ? 'portal.renewal.resume' : 'portal.renewal.cancel') }}</AppButton>
    </AppAlert>
    <AppAlert v-if="sq.first_payment_due && !sq.awaiting_payment" :tone="trialEnded ? 'warning' : 'info'" :title="t(trialEnded ? 'portal.first.endedTitle' : 'portal.first.title')" data-testid="first-payment">
      {{ t(trialEnded ? 'portal.first.endedBody' : 'portal.first.body', { date: sq.paid_until ? date(sq.paid_until, { day: 'numeric', month: 'short', year: 'numeric' }) : '' }) }}
      <span v-if="firstPackages.length > 1" style="display: grid; gap: 4px; margin-top: 10px; max-width: 320px">
        <AppField v-model="firstPkg" as="select" :label="t('portal.first.package')" :options="firstPackages.map((p) => ({ value: p, label: t(`marketing.pricing.launch.${p}.name`) }))" />
      </span>
      <VoucherField v-model="voucher" :square-id="sq.id" :preview="{ kind: 'first', interval: 'month', launch_package: firstPkg }" style="margin-top: 10px" />
      <span style="display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px">
        <span v-for="iv in (['month', 'year'] as const)" :key="iv" style="display: grid; gap: 4px; align-content: start">
          <AppButton icon="card" :variant="iv === 'month' ? 'primary' : 'secondary'" :disabled="busy" style="min-height: 44px" @click="pay({ kind: 'first', interval: iv, launch_package: firstPkg })">
            {{ t(iv === 'month' ? 'portal.first.payMonth' : 'portal.first.payYear', { amount: usd(firstAmount(iv)) }) }}
          </AppButton>
          <TaxLine :minor="firstAmount(iv)" :percent="sq.tax_percent" />
        </span>
      </span>
    </AppAlert>
    <AppAlert v-if="sq.awaiting_payment" tone="warning" :title="t('portal.eventPass.payTitle')" data-testid="event-pass-pay">
      {{ t('portal.eventPass.payBody', { amount: usd(prices.find((p) => p.key === 'launch.event')?.amount_minor ?? 0) }) }}
      <TaxLine :minor="prices.find((p) => p.key === 'launch.event')?.amount_minor ?? 0" :percent="sq.tax_percent" />
      <VoucherField v-model="voucher" :square-id="sq.id" :preview="{ kind: 'event_pass' }" style="margin-top: 10px" />
      <AppButton icon="card" class="ep-pay" :disabled="busy" style="min-height: 44px; margin-top: 10px" @click="pay({ kind: 'event_pass' })">{{ t('portal.eventPass.payButton') }}</AppButton>
    </AppAlert>

    <VoucherField v-if="sq.can_manage_billing && !sq.awaiting_payment && !sq.first_payment_due" v-model="voucher" :square-id="sq.id" />

    <EventPassCard v-if="sq.event_pass" :square="sq" :prices="prices" :busy="busy" @upgrade="(pkg, interval) => pay({ kind: 'event_upgrade', launch_package: pkg, interval })" @confirm-export="confirmExport" />

    <div v-if="sq.launch_package === 'custom' && sq.custom_amount_minor" class="pc-custom" data-testid="custom-plan">
      <div>
        <span class="rs-eyebrow">{{ t('portal.custom.eyebrow') }}</span>
        <b>{{ t(sq.custom_interval === 'year' ? 'portal.custom.perYear' : 'portal.custom.perMonth', { amount: usd(sq.custom_amount_minor) }) }}</b>
        <TaxLine :minor="sq.custom_amount_minor" :percent="sq.tax_percent" />
        <p class="bs-mute">{{ t('portal.custom.text') }}</p>
      </div>
      <AppButton v-if="sq.can_manage_billing" icon="card" :disabled="busy" style="min-height: 44px" @click="pay({ kind: 'running', running_plan: 'live', interval: sq.custom_interval === 'year' ? 'year' : 'month' })">{{ t('portal.custom.pay') }}</AppButton>
    </div>

    <PlanCards v-if="sq.launch_package !== 'custom' && !sq.awaiting_payment && !(sq.payment_required && sq.first_payment_due)" :square="sq" :prices="prices" :busy="busy" @upgrade="pay({ kind: 'upgrade', launch_package: $event })" @pay="(plan, interval) => pay({ kind: 'running', running_plan: plan, interval })" @change="askChange" @wake="change('live')" />

    <p class="bs-mute" style="margin: 0; font-size: var(--text-xs)">{{ t('portal.plan.free') }}</p>
    <ConfirmDialog v-if="dialog === 'downgrade'" tone="primary" :title="t('portal.plan.downgradeTitle')" :verb="t('portal.plan.downgradeVerb', { date: endDate })" @cancel="dialog = ''" @confirm="changePlan('keep')">
      <p class="bs-mute" style="margin: 0">{{ renewing ? t('portal.plan.downgradeBodyRenewing', { date: endDate, price: priceText('keep') }) : t('portal.plan.downgradeBodyPaid', { date: endDate }) }}</p>
    </ConfirmDialog>
    <ConfirmDialog v-if="dialog === 'upgrade'" tone="primary" :title="t('portal.plan.upgradeTitle')" :verb="t('portal.plan.upgradeVerb')" @cancel="dialog = ''" @confirm="changePlan('live')">
      <p class="bs-mute" style="margin: 0">{{ renewing ? t('portal.plan.upgradeBodyRenewing', { amount: usd(upgradeEstimate), date: endDate, price: priceText('live') }) : t('portal.plan.upgradeBodyPaid', { date: endDate }) }}</p>
    </ConfirmDialog>
  </section>
</template>

<style scoped>
.pc-custom { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px 24px; padding: 18px 20px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); }
.pc-custom div { display: grid; gap: 4px; }
.pc-custom b { font: 500 26px/1.1 var(--font-display); letter-spacing: -0.01em; }
.pc-custom p { margin: 0; font-size: var(--text-sm); }
.pc-now { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px 24px; padding: 18px 20px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); box-shadow: inset 0 2px 0 var(--color-brass); }
.pc-now__item { display: grid; gap: 6px; align-content: start; }
.pc-now__item b { font: 500 26px/1.1 var(--font-display); letter-spacing: -0.01em; color: var(--color-text); }
.pc-now__text { grid-column: 1 / -1; margin: 0; font-size: var(--text-sm); }
</style>
