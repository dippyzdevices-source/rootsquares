<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { platform, type Invoice } from '@/services/platform'
import { errorText } from '@/features/platform/errorText'
import { orderText } from './orderText'

// The invoice of one paid payment (W19-R16), after the design project's Invoice.html: an A4 sheet on screen, printed or saved as PDF with the browser's print dialog.
// It lives on its own route outside the portal shell (no header, no side bar). Every line comes from the order; what the seller left empty in the platform settings is not shown.
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const inv = ref<Invoice | null>(null)
const error = ref('')
const squareId = computed(() => String(route.params.id))
const o = computed(() => inv.value?.order ?? null)

const money = (minor: number) => new Intl.NumberFormat('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(minor / 100)
const day = (iso: string) => new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(iso))
const country = computed(() => { try { return inv.value?.country ? new Intl.DisplayNames(['en'], { type: 'region' }).of(inv.value.country) : '' } catch { return inv.value?.country ?? '' } })
const net = (gross: number) => (inv.value && inv.value.tax_percent > 0 ? Math.round((gross * 100) / (100 + inv.value.tax_percent)) : gross)
const card = computed(() => (o.value?.card_last4 ? `${(o.value.card_brand ?? '').replace(/^./, (c) => c.toUpperCase())} •••• ${o.value.card_last4}`.trim() : ''))
// the lines: the price (before a voucher), then one line per voucher discount; amounts without tax, like the totals under them
const listNet = computed(() => (o.value ? net(o.value.list_minor ?? o.value.amount_minor) : 0))
const discountNet = computed(() => (inv.value ? listNet.value - inv.value.net_minor : 0))

const print = () => window.print()

onMounted(async () => {
  try { inv.value = await platform.getInvoice(String(route.params.orderId)) } catch (e) { error.value = errorText(t, e) }
})
</script>

<template>
  <div class="iv-root">
    <div class="iv-bar">
      <a :href="`/squares/${squareId}/payments`" class="iv-back" @click.prevent="router.back()">← {{ t('portal.invoice.back') }}</a>
      <span class="iv-sp" />
      <AppButton v-if="inv" icon="receipt" @click="print">{{ t('portal.invoice.print') }}</AppButton>
    </div>
    <AppAlert v-if="error" tone="danger" :title="t('bx.errorTitle')">{{ error }}</AppAlert>
    <span v-else-if="!inv" class="bs-mute" role="status">{{ t('portal.invoice.loading') }}</span>

    <article v-if="inv && o" class="iv-sheet in" :aria-label="t('portal.invoice.title')">
      <div class="top">
        <div>
          <div class="wm">
            <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="2.2" /><path d="M12 4v9M12 9l-4 3M12 9l4 3" fill="none" stroke="var(--color-brass)" stroke-width="2.2" stroke-linecap="round" /></svg>rootsquares
          </div>
          <div v-if="inv.seller.name || inv.seller.org_no || inv.seller.address || inv.seller.email" class="co">
            <template v-if="inv.seller.name || inv.seller.org_no">{{ [inv.seller.name, inv.seller.org_no && t('portal.invoice.orgNo', { no: inv.seller.org_no })].filter(Boolean).join(' · ') }}<br></template>
            <template v-if="inv.seller.address || inv.seller.email">{{ [inv.seller.address, inv.seller.email].filter(Boolean).join(' · ') }}</template>
          </div>
        </div>
        <div class="r">
          <h1>{{ t('portal.invoice.title') }}</h1>
          <div class="rule" />
          <div class="due">{{ t(o.status === 'refunded' ? 'portal.invoice.refunded' : 'portal.invoice.paid', { date: day(inv.issued_at) }) }}</div>
        </div>
      </div>

      <div class="meta" :class="{ 'meta--3': !inv.period_start }">
        <div><span>{{ t('portal.invoice.billedTo') }}</span><b>{{ inv.buyer_name }}</b><br>{{ inv.square_name }}<template v-if="country"><br>{{ country }}</template></div>
        <div><span>{{ t('portal.invoice.number') }}</span><b>{{ inv.number }}</b></div>
        <div><span>{{ t('portal.invoice.issued') }}</span><b>{{ day(inv.issued_at) }}</b></div>
        <div v-if="inv.period_start && inv.period_end"><span>{{ t('portal.invoice.period') }}</span><b>{{ day(inv.period_start) }} – {{ day(inv.period_end) }}</b></div>
      </div>

      <table>
        <thead><tr><th>{{ t('portal.invoice.description') }}</th><th class="n">{{ t('portal.invoice.qty') }}</th><th class="n">{{ t('portal.invoice.unit') }}</th><th class="n">{{ t('portal.invoice.amount', { currency: o.currency }) }}</th></tr></thead>
        <tbody>
          <tr>
            <td>{{ orderText(t, o) }}<small v-if="inv.period_start && inv.period_end">{{ day(inv.period_start) }} – {{ day(inv.period_end) }}</small></td>
            <td class="n">1</td><td class="n">{{ money(listNet) }}</td><td class="n">{{ money(listNet) }}</td>
          </tr>
          <tr v-if="discountNet > 0">
            <td>{{ t('portal.invoice.voucher') }}<small v-if="o.voucher_code">{{ o.voucher_code }}</small></td>
            <td class="n">1</td><td class="n">−{{ money(discountNet) }}</td><td class="n">−{{ money(discountNet) }}</td>
          </tr>
        </tbody>
      </table>

      <div class="sum">
        <div class="pay">
          <b>{{ t('portal.invoice.payment') }}</b>
          <dl>
            <dt>{{ t('portal.invoice.status') }}</dt><dd>{{ t(`portal.checkout.states.${o.status}`) }}</dd>
            <dt>{{ t('portal.invoice.paidOn') }}</dt><dd>{{ day(inv.issued_at) }}</dd>
            <template v-if="card"><dt>{{ t('portal.invoice.card') }}</dt><dd>{{ card }}</dd></template>
            <template v-if="o.refunded_minor"><dt>{{ t('portal.invoice.refundedAmount') }}</dt><dd>{{ o.currency }} {{ money(o.refunded_minor) }}</dd></template>
          </dl>
        </div>
        <div class="tot">
          <template v-if="inv.tax_percent > 0">
            <div><span class="l">{{ t('portal.invoice.subtotal') }}</span><span>{{ money(inv.net_minor) }}</span></div>
            <div><span class="l">{{ t('portal.invoice.vat', { percent: inv.tax_percent }) }}</span><span>{{ money(inv.tax_minor) }}</span></div>
          </template>
          <div class="tt"><span>{{ t('portal.invoice.total') }}</span><b>{{ o.currency }} {{ money(o.amount_minor) }}</b></div>
        </div>
      </div>

      <p v-if="inv.seller.footer" class="note">{{ inv.seller.footer }}</p>

      <div class="foot">
        <span v-if="inv.seller.email">{{ t('portal.invoice.questions', { email: inv.seller.email, number: inv.number }) }}</span>
        <span v-else>{{ inv.number }}</span>
      </div>
    </article>
  </div>
</template>

<style scoped>
.iv-root { position: fixed; inset: 0; z-index: 30; overflow: auto; background: var(--color-surface-sunken); padding: 16px 16px 40px; }
.iv-bar { display: flex; align-items: center; gap: 12px; max-width: 210mm; margin: 0 auto 14px; }
.iv-back { font-size: var(--text-sm); }
.iv-sp { flex: 1; }
.iv-root > .bs-mute, .iv-root > :deep(.rs-alert) { display: block; max-width: 210mm; margin: 0 auto; }

/* the sheet is the design's A4 page (Invoice.html); mm sizes so the screen and the print agree */
.in { background: var(--color-surface); color: var(--color-text); font: 400 12px/1.5 var(--font-sans); padding: 14mm 16mm 12mm; display: flex; flex-direction: column; gap: 8mm; box-sizing: border-box; width: 210mm; max-width: 100%; min-height: 297mm; margin: 0 auto; box-shadow: var(--shadow-md); }
.top { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
.wm { display: flex; align-items: center; gap: 8px; font: 600 19px var(--font-heading); letter-spacing: -0.015em; }
.co { margin-top: 10px; font-size: 11px; color: var(--color-text-muted); line-height: 1.5; }
.r { text-align: right; }
h1 { font: 500 46px/1 var(--font-display); letter-spacing: -0.01em; margin: 0; }
.rule { width: 56px; height: 1px; background: var(--color-brass); margin: 10px 0 8px auto; }
.due { font: 500 10.5px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-brass-text); }
.meta { display: grid; grid-template-columns: 1.3fr 1fr 1fr 1fr; gap: 16px; border-top: 1px solid var(--color-text); border-bottom: 1px solid var(--color-border); padding: 12px 0; }
.meta--3 { grid-template-columns: 1.3fr 1fr 1fr; }
.meta span, th, .pay b { font: 500 9.5px/1 var(--font-sans); letter-spacing: 0.12em; text-transform: uppercase; color: var(--color-text-muted); }
.meta span { display: block; margin-bottom: 6px; }
.meta b { font-weight: 500; font-size: 12.5px; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 0 0 8px; border-bottom: 1px solid var(--color-text); }
td { padding: 8px 0; border-bottom: 1px solid var(--color-border); vertical-align: top; }
td small { display: block; color: var(--color-text-muted); font-size: 10.5px; }
.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
th.n { text-align: right; }
.sum { display: grid; grid-template-columns: 1fr 78mm; gap: 12mm; align-items: start; }
.pay { background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--shape-surface); padding: 12px 16px; font-size: 11.5px; }
.pay b { display: block; margin-bottom: 8px; }
.pay dl { display: grid; grid-template-columns: auto 1fr; gap: 3px 14px; margin: 0; }
.pay dt { color: var(--color-text-muted); }
.pay dd { margin: 0; font-weight: 500; }
.tot div { display: flex; justify-content: space-between; padding: 5px 0; font-variant-numeric: tabular-nums; }
.tot .l { color: var(--color-text-muted); }
.tot .tt { border-top: 1px solid var(--color-text); margin-top: 6px; padding-top: 10px; align-items: baseline; }
.tot .tt span { font: 500 9.5px var(--font-sans); letter-spacing: 0.12em; text-transform: uppercase; }
.tot .tt b { font: 600 28px/1 var(--font-heading); letter-spacing: -0.015em; }
.note { margin: 0; font-size: 10.5px; color: var(--color-text-muted); }
.foot { margin-top: auto; border-top: 1px solid var(--color-border); padding-top: 10px; display: flex; justify-content: space-between; gap: 16px; color: var(--color-text-muted); font-size: 10.5px; }

@media (max-width: 720px) {
  .in { padding: 20px 16px; min-height: 0; }
  .top { flex-direction: column; }
  .r { text-align: left; }
  .rule { margin-left: 0; }
  .meta, .meta--3 { grid-template-columns: 1fr 1fr; }
  .sum { grid-template-columns: 1fr; gap: 20px; }
}
@media print {
  @page { size: A4; margin: 0; }
  .iv-root { position: static; padding: 0; background: none; overflow: visible; }
  .iv-bar { display: none; }
  .in { box-shadow: none; width: 210mm; min-height: 297mm; }
}
</style>
