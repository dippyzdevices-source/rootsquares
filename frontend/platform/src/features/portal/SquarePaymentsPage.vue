<script setup lang="ts">
import { orderText } from './orderText'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SegToggle from '@/components/ui/SegToggle.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import { platform, type BillingOrder, type PlanPrice } from '@/services/platform'
import { usd } from '@rootsquares/ui/mock/pricing'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/features/platform/errorText'
import { useSquare } from './squareContext'

// Payments page (W10-R46): where a square's money is handled, apart from choosing the plan (Billing). The state of the paid period (trial, paid until), the default
// billing period (what the plan cards offer first), the payment history, and the place for the card and receipts once Stripe is switched on (docs/setup/22-stripe-billing.md).
// W23-R41: redesigned from the design project's `Square Payments Redesign.html` (the paid period with a progress bar beside the billing-period switch, a compact
// payment history, the card and receipts row); the blue test-mode banner stays, as the user asked. Before: W13-R41, console cards.
const { t } = useI18n()
const { push } = useToast()
const { date } = useFormat()
const { sq, set } = useSquare()
const orders = ref<BillingOrder[]>([])
const loading = ref(true)
const error = ref('')
const interval = ref<'month' | 'year'>('month')
const prices = ref<PlanPrice[]>([])
// A change of the default billing period is asked for first (W23-R60): the switch only opens the dialog, nothing is saved until the user confirms.
const pending = ref<'month' | 'year' | null>(null)
const full = { day: 'numeric', month: 'short', year: 'numeric' } as const

const until = computed(() => (sq.value?.paid_until ? new Date(sq.value.paid_until) : null))
const running = computed(() => !!until.value && until.value > new Date())
const hasPaid = computed(() => orders.value.some((o) => o.status === 'paid'))
const period = computed(() => (!sq.value || sq.value.running_plan === 'event' ? 'event' : running.value ? (hasPaid.value ? 'paid' : 'trial') : 'none'))
const cardBrand = (b?: string | null) => (b ? b.charAt(0).toUpperCase() + b.slice(1) : t('portal.payments.card'))
const tone = (s: string) => (s === 'paid' ? 'ok' : s === 'pending' ? 'warn' : s === 'refunded' ? 'info' : 'mute')
const orderLabel = (o: BillingOrder) => orderText(t, o)

// The bar runs from the first payment (or the day the square was made) to the end of the paid period.
const startedAt = computed(() => {
  const paid = orders.value.filter((o) => o.status === 'paid').map((o) => new Date(o.created_at).getTime())
  return paid.length ? new Date(Math.min(...paid)) : sq.value ? new Date(sq.value.created_at) : null
})
const progress = computed(() => {
  if (!until.value || !startedAt.value) return 0
  const span = until.value.getTime() - startedAt.value.getTime()
  return span > 0 ? Math.min(100, Math.max(0, Math.round(((Date.now() - startedAt.value.getTime()) / span) * 100))) : 0
})
// The history shows the latest three until it is opened.
const showAll = ref(false)
const shown = computed(() => (showAll.value ? orders.value : orders.value.slice(0, 3)))

onMounted(async () => {
  if (!sq.value) return
  interval.value = sq.value.billing_interval === 'year' ? 'year' : 'month'
  try { orders.value = await platform.listOrders(sq.value.id) } catch (e) { error.value = errorText(t, e) } finally { loading.value = false }
  try { prices.value = await platform.getPrices() } catch { /* the dialog then shows no amounts */ }
})

const opening = ref(false)
async function openPortal() {
  if (!sq.value) return
  opening.value = true
  error.value = ''
  try { window.location.assign((await platform.billingPortal(sq.value.id)).url) } catch (e) { error.value = errorText(t, e); opening.value = false }
}

const periodName = (v: 'month' | 'year') => (v === 'year' ? `${t('marketing.pricing.yearly')} · ${t('marketing.pricing.save')}` : t('marketing.pricing.monthly'))
const planPrice = (v: 'month' | 'year') => prices.value.find((p) => p.key === `running.${sq.value?.running_plan}.${v}`)?.amount_minor
const hasPrices = computed(() => planPrice('month') != null && planPrice('year') != null)
function askInterval(v: 'month' | 'year') { if (v !== interval.value) pending.value = v }
async function confirmInterval() {
  const v = pending.value
  pending.value = null
  if (v) await saveInterval(v)
}

async function saveInterval(v: 'month' | 'year') {
  if (!sq.value) return
  const before = interval.value
  interval.value = v
  try {
    set(await platform.setBillingInterval(sq.value.id, v))
    push(t('portal.payments.intervalSaved'), 'success')
  } catch (e) { interval.value = before; error.value = errorText(t, e) }
}
</script>

<template>
  <div v-if="sq" style="display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px" data-testid="payments-page">
    <div class="bw-hd">
      <h2 class="bs-h2" style="font-size: 28px; margin: 0">{{ t('portal.payments.title') }}</h2>
      <p class="bs-mute" style="margin: 4px 0 0; font-size: var(--text-sm)">{{ t('portal.payments.lede') }}</p>
    </div>
    <AppAlert tone="info">{{ t('portal.plan.free') }}</AppAlert>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>

    <div class="pm-top">
      <section class="pm-card" data-testid="paid-period">
        <h3>{{ t('portal.payments.periodTitle') }}</h3>
        <p v-if="period === 'trial'" class="pm-big">{{ t('portal.payments.trial', { date: date(sq.paid_until!, full) }) }}</p>
        <p v-else-if="period === 'paid'" class="pm-big">{{ t('portal.payments.paidUntil', { date: date(sq.paid_until!, full) }) }}</p>
        <p v-else-if="period === 'event'" class="pm-big">{{ t('portal.payments.event') }}</p>
        <p v-else class="pm-big">{{ t('portal.payments.none') }}</p>
        <template v-if="until && (period === 'trial' || period === 'paid')">
          <div class="pm-prog" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100"><i :style="{ width: `${progress}%` }" /></div>
          <div class="pm-pl"><span v-if="startedAt">{{ t('squarePayments.started', { date: date(startedAt, full) }) }}</span></div>
        </template>
        <p class="pm-text">{{ t(`portal.payments.${period}Text`) }}</p>
        <AppButton icon="card" class="pm-btn" :to="`/squares/${sq.id}/billing`">{{ t('portal.payments.changePlan') }}</AppButton>
      </section>
      <section class="pm-card">
        <h3>{{ t('portal.payments.intervalTitle') }}</h3>
        <SegToggle :model-value="interval" :label="t('marketing.pricing.period')" :items="[['month', t('marketing.pricing.monthly')], ['year', `${t('marketing.pricing.yearly')} · ${t('marketing.pricing.save')}`]]" @update:model-value="askInterval($event as 'month' | 'year')" />
        <p class="pm-text">{{ t('portal.payments.intervalText') }}</p>
      </section>
    </div>

    <section class="pm-card pm-hist">
      <div class="pm-hist__t"><h3>{{ t('portal.payments.historyTitle') }}</h3><span v-if="orders.length">{{ t('squarePayments.count', { n: shown.length, total: orders.length }) }}</span></div>
      <div v-if="!loading && !orders.length"><EmptyState icon="receipt" :title="t('portal.payments.noPayments')">{{ t('portal.payments.noPaymentsText') }}</EmptyState></div>
      <div v-for="o in shown" v-else :key="o.id" class="pm-row" role="listitem">
        <div>
          <b>{{ orderLabel(o) }}</b>
          <small>{{ date(o.created_at, full) }}<template v-if="o.card_last4"> · {{ cardBrand(o.card_brand) }} ···· {{ o.card_last4 }}</template></small>
        </div>
        <span class="pm-amt">{{ usd(o.amount_minor) }}</span>
        <RouterLink v-if="o.status === 'paid' || o.status === 'refunded'" :to="`/squares/${sq.id}/invoice/${o.id}`" class="pm-inv">{{ t('portal.invoice.link') }}</RouterLink>
        <span v-else />
        <OcPill :tone="tone(o.status)">{{ t(`portal.checkout.states.${o.status}`) }}</OcPill>
      </div>
      <button v-if="orders.length > 3" type="button" class="pm-more" @click="showAll = !showAll">{{ showAll ? t('squarePayments.fewer') : t('squarePayments.all') }}</button>
    </section>

    <section class="pm-card pm-method">
      <div><b>{{ t('portal.payments.methodTitle') }}</b><span>{{ t(sq.can_manage_billing ? 'portal.payments.methodReady' : 'portal.payments.methodText') }}</span></div>
      <AppButton v-if="sq.can_manage_billing" icon="card" class="pm-btn pm-btn--o" variant="secondary" :loading="opening" @click="openPortal">{{ t('portal.payments.methodButton') }}</AppButton>
    </section>

    <ConfirmDialog v-if="pending" tone="primary" roomy :title="t('squarePayments.confirmTitle')" :verb="t('squarePayments.confirmVerb', { period: pending === 'year' ? t('marketing.pricing.yearly') : t('marketing.pricing.monthly') })" @cancel="pending = null" @confirm="confirmInterval">
      <dl class="pm-dl">
        <dt>{{ t('squarePayments.from') }}</dt><dd>{{ periodName(interval) }}</dd>
        <dt>{{ t('squarePayments.to') }}</dt><dd><b>{{ periodName(pending) }}</b></dd>
        <template v-if="hasPrices && (sq.running_plan === 'live' || sq.running_plan === 'keep')">
          <dt>{{ t('squarePayments.yourPlan') }}</dt>
          <dd>{{ t(`marketing.pricing.running.${sq.running_plan}.name`) }}: {{ usd(planPrice('month')!) }} {{ t('marketing.pricing.perMonth') }} · {{ usd(planPrice('year')!) }} {{ t('marketing.pricing.perYear') }}</dd>
        </template>
      </dl>
      <p><b>{{ t('squarePayments.changesTitle') }}</b> {{ t('squarePayments.changesText', { period: pending === 'year' ? t('marketing.pricing.yearly') : t('marketing.pricing.monthly') }) }}</p>
      <p><b>{{ t('squarePayments.keepsTitle') }}</b> {{ t('squarePayments.keepsText') }}</p>
    </ConfirmDialog>
  </div>
</template>

<style scoped>
/* Tokens only: the design's cream, rust and green are mapped to the theme (brass, success); shapes come from shape.css. */
.pm-top { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 14px; }
.pm-card { padding: 20px 24px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); }
.pm-card h3 { margin: 0 0 10px; font: 600 10px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-text-muted); }
.pm-big { margin: 0; font: 400 36px/1.1 var(--font-display); }
.pm-text { margin: 6px 0 16px; color: var(--color-text-muted); font-size: var(--text-sm); }
.pm-card :deep(.bt-seg) { margin-block: 14px; }
.pm-prog { height: 6px; margin: 14px 0 4px; overflow: hidden; border-radius: var(--shape-control); background: var(--color-border); }
.pm-prog i { display: block; height: 100%; border-radius: var(--shape-control); background: var(--color-success); }
.pm-pl { display: flex; justify-content: space-between; color: var(--color-text-muted); font-size: var(--text-xs); }
/* The buttons of the design: capitals, 11px. The filled one is the theme's dark primary; the outlined one has a light outline. */
.pm-btn.pm-btn { padding: 0 20px; border-radius: var(--shape-control); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.pm-btn--o.pm-btn--o { border-color: var(--color-border); background: var(--color-surface); color: var(--color-text); }
.pm-btn--o.pm-btn--o:hover { border-color: var(--color-brass); background: var(--color-surface-sunken); }
.pm-hist { padding: 18px 24px 0; }
.pm-hist__t { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 6px; }
.pm-hist__t h3 { margin: 0; }
.pm-hist__t span { font-size: var(--text-xs); color: var(--color-text-muted); }
.pm-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto auto; gap: 18px; align-items: center; padding: 12px 0; border-top: 1px solid var(--color-border); }
.pm-row b { display: block; font-weight: 600; }
.pm-row small { color: var(--color-text-muted); font-size: var(--text-xs); }
.pm-amt { min-width: 56px; font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; }
.pm-inv { font-size: var(--text-sm); font-weight: 500; color: var(--color-brass-text); text-decoration: none; }
.pm-inv:hover { text-decoration: underline; }
.pm-more { display: block; width: calc(100% + 48px); margin: 0 -24px; padding: 14px; border: 0; border-top: 1px solid var(--color-border); border-radius: 0 0 var(--shape-surface) var(--shape-surface); background: none; color: var(--color-brass-text); font: 600 12px var(--font-sans); letter-spacing: 0.06em; cursor: pointer; }
.pm-more:hover { background: var(--color-surface-sunken); }
.pm-dl { display: grid; grid-template-columns: max-content 1fr; gap: 10px 20px; padding: 14px 16px; border: 1px solid var(--color-border); border-radius: var(--shape-inner); background: var(--color-surface-sunken); margin: 0; font-size: var(--text-sm); }
.pm-dl dt { color: var(--color-text-muted); }
.pm-dl dd { margin: 0; }
.pm-method { display: flex; gap: 16px; align-items: center; justify-content: space-between; flex-wrap: wrap; padding: 16px 24px; }
.pm-method b { display: block; }
.pm-method span { color: var(--color-text-muted); font-size: var(--text-sm); }
@media (max-width: 700px) { .pm-top { grid-template-columns: minmax(0, 1fr); } .pm-row { grid-template-columns: minmax(0, 1fr) auto; gap: 6px 14px; } .pm-inv { grid-column: 1; } .pm-row :deep(.oc-pill) { justify-self: end; } }
</style>
