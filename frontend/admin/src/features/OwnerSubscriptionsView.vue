<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import OcHead from '@/components/OcHead.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { usd } from '@rootsquares/ui/mock/pricing'
import { type OwnerSubscriptions, type SubsUpcoming } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'
import { errorText } from '@/errorText'

// Owner console, Subscriptions (W12-R20): real money and plan state of every square, in US dollars, read from the platform's own tables (orders, plans, dates):
// recurring revenue, paying squares, trials, failed payments, the packages and running plans in use, and what renews next. Restyled in W11-R75 from
// "Console Subscriptions.html": large figures in the platform's figure style (ADR 045), a View state switch, loading and error states that keep the page's shape.
const { t } = useI18n()
const { date } = useFormat()
const data = ref<OwnerSubscriptions | null>(null)
const loading = ref(true)
const failed = ref('')
const forced = ref('default')
async function load() {
  loading.value = true
  failed.value = ''
  try { data.value = await platform.ownerSubscriptions() } catch (e) { failed.value = errorText(t, e) }
  loading.value = false
}
onMounted(load)
const view = computed(() => (forced.value !== 'default' ? forced.value : loading.value ? 'loading' : failed.value ? 'error' : 'default'))

const kpis = computed(() => {
  const d = data.value
  return [
    { l: t('own.kpiMrr'), v: usd(d?.mrr_minor ?? 0), d: t('own.kpiMrrNote', { amount: usd(d?.paid_30d_minor ?? 0) }), c: '' },
    { l: t('own.kpiPaying'), v: String(d?.paying ?? 0), d: t('own.kpiPayingNote', { n: d?.asleep ?? 0 }), c: '' },
    { l: t('own.kpiTrial'), v: String(d?.trial ?? 0), d: t('own.kpiTrialNote'), c: '' },
    { l: t('own.kpiPastDue'), v: String(d?.failed ?? 0), d: t('own.kpiPastDueNote'), c: (d?.failed ?? 0) > 0 ? 'dn' : '' },
  ]
})
const packages = computed(() => data.value?.packages ?? [])
const running = computed(() => (data.value?.running ?? []).filter((r) => r.key === 'live' || r.key === 'keep'))
const maxPackages = computed(() => Math.max(1, ...packages.value.map((x) => x.count)))
const maxRunning = computed(() => Math.max(1, ...running.value.map((x) => x.count)))
const upcoming = computed(() => data.value?.upcoming ?? [])
const TONE: Record<SubsUpcoming['state'], 'ok' | 'warn' | 'info' | 'bad'> = { renewing: 'ok', paid: 'ok', trial: 'info', ending: 'warn', failed: 'bad', unpaid: 'warn', asleep: 'warn', expired: 'bad' }
const empty = computed(() => !loading.value && !failed.value && !upcoming.value.length && !packages.value.some((p) => p.count))
</script>

<template>
  <OcHead :title="t('own.subsTitle')" :sub="t('own.subsSub')" />

  <div v-if="view === 'error'" class="oc-card" style="padding: 28px 18px; text-align: center">
    <b style="display: block; color: var(--color-danger); margin-bottom: 4px">{{ t('own.errorTitle') }}</b>
    <span class="oc-mut">{{ failed || t('own.errorText') }}</span><br>
    <button type="button" class="oc-btn" style="margin-top: 14px" @click="forced = 'default'; load()"><AppIcon name="refresh" :size="14" />{{ t('bx.retry') }}</button>
  </div>
  <template v-else>
    <div class="ov-kpi" style="margin-top: 18px">
      <div v-for="(k, i) in kpis" :key="k.l" class="ov-card ov-k" :class="i === 0 && 'ov-k--hero'">
        <template v-if="view === 'loading'"><span class="bx-sk" style="height: 10px; width: 40%" /><span class="bx-sk" style="height: 34px; width: 70%; margin-top: 12px" /></template>
        <template v-else><small>{{ k.l }}</small><em class="ov-num">{{ k.v }}</em><span class="oc-kpi-d" :class="k.c">{{ k.d }}</span></template>
      </div>
    </div>
    <p v-if="empty" class="oc-mut" style="margin-top: 14px">{{ t('own.subsEmpty') }}</p>
    <div class="oc-grid2" style="margin-top: 12px">
      <section class="oc-card">
        <h3 class="oc-h3">{{ t('own.packages') }}</h3>
        <div v-for="x in packages" :key="x.key" class="oc-li">
          <div style="flex: 1; min-width: 0">
            <b>{{ t(`marketing.pricing.${x.key === 'event' ? 'running.event' : `launch.${x.key}`}.name`) }}</b> <span class="oc-mut">{{ usd(x.price_minor) }}</span>
            <span v-if="view === 'loading'" class="bx-sk" style="display: block; height: 6px; width: 140px; margin-top: 8px" />
            <div v-else class="oc-bar"><i :style="{ width: (x.count / maxPackages) * 100 + '%' }" /></div>
          </div>
          <span style="font-variant-numeric: tabular-nums">{{ view === 'loading' ? '…' : t('own.squaresCount', { n: x.count }) }}</span>
        </div>
        <h3 class="oc-h3" style="margin-top: 18px">{{ t('own.runningPlans') }}</h3>
        <div v-for="x in running" :key="x.key" class="oc-li">
          <div style="flex: 1; min-width: 0">
            <b>{{ t(`marketing.pricing.running.${x.key}.name`) }}</b> <span class="oc-mut">{{ t('own.perMonth', { price: usd(x.price_minor) }) }}</span>
            <span v-if="view === 'loading'" class="bx-sk" style="display: block; height: 6px; width: 140px; margin-top: 8px" />
            <div v-else class="oc-bar"><i :style="{ width: (x.count / maxRunning) * 100 + '%' }" /></div>
          </div>
          <span style="font-variant-numeric: tabular-nums">{{ view === 'loading' ? '…' : t('own.squaresCount', { n: x.count }) }}</span>
        </div>
      </section>
      <section class="oc-card">
        <h3 class="oc-h3">{{ t('own.renewals') }}<RouterLink to="/squares" style="text-transform: none; letter-spacing: 0; font-size: var(--text-sm)">{{ t('own.all') }}</RouterLink></h3>
        <p v-if="!loading && !upcoming.length" class="oc-mut" style="margin: 0; padding: 28px 18px 32px">{{ t('own.noRenewals') }}</p>
        <div v-for="r in upcoming" :key="r.square_id" class="oc-li">
          <span class="oc-dt">{{ r.paid_until ? date(r.paid_until, { day: 'numeric', month: 'short' }) : '' }}</span>
          <div style="flex: 1; min-width: 0">
            <RouterLink :to="`/squares/${r.square_id}`"><b>{{ r.name }}</b></RouterLink>
            <small>{{ r.next_minor ? usd(r.next_minor) : t('own.noNext') }}</small>
          </div>
          <OcPill :tone="TONE[r.state]">{{ t(`own.subState.${r.state}`) }}</OcPill>
        </div>
      </section>
    </div>
  </template>
</template>
