<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import AppTabs from '@rootsquares/ui/components/AppTabs.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import OcHead from '@/components/OcHead.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { errorText } from '@/errorText'
import { usd } from '@rootsquares/ui/mock/pricing'
import { type OpexActual, type OpexCadence, type OpexForecast, type OpexInput, type OpexItem, type OpexMonthly, type OpexRate, type OpexScenarioName } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'

// Owner console, Costs (W16-R9, docs/plans/opex-plan.md): the platform's own running costs. Cost lines on one tab, the year spread over the months on the other.
// Amounts are US dollars (the billing currency). The monthly grid is the plan: every line placed by its rhythm.
const { t } = useI18n()
const { push } = useToast()
const tab = ref<'costs' | 'monthly' | 'forecast'>('costs')
const tabs = computed(() => [{ id: 'costs', label: t('own.opex.tabCosts') }, { id: 'monthly', label: t('own.opex.tabMonthly') }, { id: 'forecast', label: t('own.opex.tabForecast') }])

const items = ref<OpexItem[]>([])
const categories = ref<string[]>([])
const loading = ref(true)
const error = ref('')
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : items.value.length ? 'default' : 'empty'))
async function load() {
  loading.value = true
  try {
    const list = await platform.listOpex()
    items.value = list.items
    categories.value = list.categories
    error.value = ''
  } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}

// ---- showing amounts in NOK or INR (indication only; everything stored stays in US dollars)
type Shown = 'USD' | 'NOK' | 'INR'
const shown = ref<Shown>('USD')
const rates = ref<OpexRate[]>([])
const rate = computed(() => rates.value.find((r) => r.code === shown.value) ?? null)
const shownChoices = [{ value: 'USD', label: 'USD' }, { value: 'NOK', label: 'NOK' }, { value: 'INR', label: 'INR' }]
function fmt(minor: number): string {
  const r = rate.value
  if (shown.value === 'USD' || !r) return usd(minor)
  return new Intl.NumberFormat(shown.value === 'INR' ? 'en-IN' : 'nb-NO', { style: 'currency', currency: shown.value, maximumFractionDigits: 0 }).format((minor / 100) * r.rate)
}
async function loadRates() { try { rates.value = await platform.opexRates() } catch (e) { push(errorText(t, e), 'danger') } }
async function refreshRates() {
  try { rates.value = await platform.refreshOpexRates(); push(t('own.opex.ratesRefreshed'), 'success') } catch (e) { push(errorText(t, e), 'danger') }
}
const typedRate = ref('')
async function useTypedRate() {
  const n = Number(typedRate.value.replace(',', '.'))
  if (shown.value === 'USD' || !Number.isFinite(n) || n <= 0) { push(t('own.opex.badRate'), 'danger'); return }
  try { rates.value = await platform.setOpexRate(shown.value, n); typedRate.value = '' } catch (e) { push(errorText(t, e), 'danger') }
}
const rateNote = computed(() => {
  const r = rate.value
  if (shown.value === 'USD') return ''
  return r ? t('own.opex.ratesNote', { rate: r.rate, code: r.code, date: r.date, source: t(`own.opex.ratesSource.${r.source}`) }) : t('own.opex.noRates', { code: shown.value })
})

// ---- the monthly grid
const year = ref(new Date().getFullYear())
const monthly = ref<OpexMonthly | null>(null)
const monthlyError = ref('')
async function loadMonthly() {
  try { monthly.value = await platform.opexMonthly(year.value); monthlyError.value = '' } catch (e) { monthlyError.value = errorText(t, e) }
}
const months = computed(() => Array.from({ length: 12 }, (_, i) => new Intl.DateTimeFormat('en-US', { month: 'short' }).format(new Date(2000, i, 1))))
const cell = (minor: number) => (minor ? fmt(minor) : '–')
const change = computed(() => {
  const m = monthly.value
  if (!m || !m.previous_total) return ''
  const pct = Math.round(((m.total - m.previous_total) / m.previous_total) * 100)
  return t('own.opex.vsLastYear', { pct: `${pct > 0 ? '+' : ''}${pct}`, last: fmt(m.previous_total) })
})
async function downloadCsv() {
  try {
    const text = await platform.opexCsv(year.value)
    const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }))
    const a = Object.assign(document.createElement('a'), { href: url, download: `opex-${year.value}.csv` })
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) { push(errorText(t, e), 'danger') }
}

onMounted(async () => { await load(); await loadMonthly(); await loadActuals(); await loadRates(); await loadNext12() })
watch(year, loadMonthly)
watch(tab, (v) => { if (v === 'monthly') void loadMonthly(); if (v === 'forecast') void loadForecast() })

// ---- the forecast
const scenario = ref<OpexScenarioName>('base')
const horizon = ref('12')
const forecast = ref<OpexForecast | null>(null)
const forecastError = ref('')
interface AForm { cash: string; rows: Record<OpexScenarioName, { add: string; churn: string; arpu: string }> }
const assume = ref<AForm | null>(null)
const assumeError = ref('')
const scenarioNames = ['low', 'base', 'high'] as const
const scenarioLabel = (n: OpexScenarioName) => t(`own.opex.sc${n[0]!.toUpperCase()}${n.slice(1)}`)
const scenarioChoices = computed(() => scenarioNames.map((n) => ({ id: n, label: scenarioLabel(n) })))
const horizonChoices = ['6', '12', '24'].map((n) => ({ value: n, label: n }))
const money = (minor: number) => (minor < 0 ? `-${fmt(-minor)}` : fmt(minor))
const monthLabel = (ym: string) => new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(new Date(`${ym}-01T00:00:00`))
function fillAssume(a: OpexForecast['assumptions']) {
  const row = (n: OpexScenarioName) => {
    const arpu = a.scenarios[n].revenue_per_square_minor
    return { add: String(a.scenarios[n].new_per_month), churn: String(a.scenarios[n].churn_pct), arpu: arpu === null ? '' : (arpu / 100).toFixed(2) }
  }
  assume.value = { cash: (a.opening_cash_minor / 100).toFixed(2), rows: { low: row('low'), base: row('base'), high: row('high') } }
}
async function loadForecast() {
  try {
    forecast.value = await platform.opexForecast(scenario.value, Number(horizon.value))
    if (!assume.value) fillAssume(forecast.value.assumptions)
    forecastError.value = ''
  } catch (e) { forecastError.value = errorText(t, e) }
}
watch([scenario, horizon], () => { if (tab.value === 'forecast') void loadForecast() })
watch(items, () => { void loadNext12() })
async function saveAssumptions() {
  const f = assume.value
  if (!f) return
  const cash = Number(f.cash.replace(',', '.'))
  const scenarios = {} as Record<OpexScenarioName, { new_per_month: number; churn_pct: number; revenue_per_square_minor: number | null }>
  for (const n of scenarioNames) {
    const r = f.rows[n], add = Number(r.add.replace(',', '.')), churn = Number(r.churn.replace(',', '.'))
    const arpu = r.arpu.trim() === '' ? null : toMinor(r.arpu)
    if (!Number.isFinite(add) || add < 0 || !Number.isFinite(churn) || churn < 0 || churn > 100 || (r.arpu.trim() !== '' && arpu === null)) { assumeError.value = t('own.opex.badAssumptions'); return }
    scenarios[n] = { new_per_month: add, churn_pct: churn, revenue_per_square_minor: arpu }
  }
  if (!Number.isFinite(cash) || f.cash.trim() === '') { assumeError.value = t('own.opex.badAssumptions'); return }
  busy.value = true
  try {
    await platform.saveOpexAssumptions({ opening_cash_minor: Math.round(cash * 100), scenarios })
    assumeError.value = ''
    push(t('own.opex.saved'), 'success')
    await loadForecast()
  } catch (e) { assumeError.value = errorText(t, e) } finally { busy.value = false }
}

// ---- real amounts
const actuals = ref<OpexActual[]>([])
const real = ref<{ item_id: string; month: string; amount: string } | null>(null)
const realError = ref('')
const fixedChoices = computed(() => items.value.filter((i) => i.cost_type !== 'variable').map((i) => ({ value: i.id, label: i.name })))
async function loadActuals() { try { actuals.value = await platform.listOpexActuals() } catch (e) { monthlyError.value = errorText(t, e) } }
function openReal() {
  const first = fixedChoices.value[0]
  real.value = { item_id: first?.value ?? '', month: `${year.value}-${String(new Date().getMonth() + 1).padStart(2, '0')}`, amount: '' }
  realError.value = ''
}
async function saveReal() {
  const r = real.value
  if (!r) return
  const minor = toMinor(r.amount)
  if (!r.item_id || !/^\d{4}-(0[1-9]|1[0-2])$/.test(r.month) || minor === null) { realError.value = t('own.opex.badReal'); return }
  busy.value = true
  try {
    await platform.recordOpexActual({ item_id: r.item_id, month: r.month, amount_minor: minor })
    real.value = null
    push(t('own.opex.recorded'), 'success')
    await Promise.all([loadActuals(), loadMonthly()])
  } catch (e) { realError.value = errorText(t, e) } finally { busy.value = false }
}
async function removeReal(a: OpexActual) {
  try { await platform.deleteOpexActual(a.id); await Promise.all([loadActuals(), loadMonthly()]) } catch (e) { push(errorText(t, e), 'danger') }
}
const differs = computed(() => !!monthly.value && monthly.value.totals.some((v, i) => v !== monthly.value!.planned_totals[i]))

// ---- the form
interface CForm { id: string | null; kind: 'fixed' | 'variable'; share: string; perOrder: string; name: string; category: string; amount: string; cadence: OpexCadence; start_on: string; end_on: string; pct: string; vendor: string; note: string }
const form = ref<CForm | null>(null)
const formError = ref('')
const busy = ref(false)
const today = () => new Date().toISOString().slice(0, 10)
function openNew() { form.value = { id: null, kind: 'fixed', share: '0', perOrder: '0', name: '', category: categories.value[0] ?? 'Other', amount: '', cadence: 'monthly', start_on: today(), end_on: '', pct: '0', vendor: '', note: '' }; formError.value = '' }
function openEdit(i: OpexItem) {
  form.value = { id: i.id, kind: i.cost_type ?? 'fixed', share: String((i.variable_bp ?? 0) / 100), perOrder: ((i.variable_fixed_minor ?? 0) / 100).toFixed(2), name: i.name, category: i.category, amount: (i.amount_minor / 100).toFixed(2), cadence: i.cadence, start_on: i.start_on, end_on: i.end_on ?? '', pct: String(i.annual_increase_pct), vendor: i.vendor ?? '', note: i.note ?? '' }
  formError.value = ''
}
function toMinor(text: string): number | null {
  const n = Number(text.replace(',', '.'))
  return text.trim() !== '' && Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : null
}
async function save() {
  const f = form.value
  if (!f) return
  const variable = f.kind === 'variable'
  const minor = variable ? 0 : toMinor(f.amount)
  const share = Number(f.share.replace(',', '.'))
  const perOrder = toMinor(f.perOrder || '0')
  const pct = variable ? 0 : Number(f.pct)
  if (variable && (!Number.isFinite(share) || share < 0 || share > 100 || perOrder === null)) { formError.value = t('own.opex.badForm'); return }
  if (!f.name.trim() || !f.category.trim() || minor === null || !f.start_on || !Number.isInteger(pct) || pct < 0 || pct > 100) { formError.value = t('own.opex.badForm'); return }
  const input: OpexInput = { name: f.name.trim(), category: f.category.trim(), amount_minor: minor, cadence: f.cadence, start_on: f.start_on, end_on: f.end_on || null, annual_increase_pct: pct, vendor: f.vendor.trim() || null, note: f.note.trim() || null, cost_type: f.kind, variable_bp: variable ? Math.round(share * 100) : 0, variable_fixed_minor: variable ? (perOrder ?? 0) : 0 }
  busy.value = true
  try {
    if (f.id) {
      const clearable = ['end_on', 'vendor', 'note'] as const
      const clear = clearable.filter((k) => input[k] === null)
      const body = Object.fromEntries(Object.entries(input).filter(([, v]) => v !== null))
      await platform.updateOpex(f.id, { ...(body as Partial<OpexInput>), clear })
    } else { await platform.createOpex(input) }
    form.value = null
    push(t('own.opex.saved'), 'success')
    await load()
    await loadMonthly()
  } catch (e) { formError.value = errorText(t, e) } finally { busy.value = false }
}

// ---- delete (asks first)
const removing = ref<OpexItem | null>(null)
async function remove() {
  const r = removing.value
  if (!r) return
  try { await platform.deleteOpex(r.id); removing.value = null; push(t('own.opex.removed'), 'success'); await load(); await loadMonthly() } catch (e) { push(errorText(t, e), 'danger') }
}

const kindChoices = computed(() => [{ value: 'fixed', label: t('own.opex.typeFixed') }, { value: 'variable', label: t('own.opex.typeVariable') }])
const cadenceChoices = computed(() => (['monthly', 'quarterly', 'yearly', 'one_off'] as const).map((c) => ({ value: c, label: t(`own.opex.cadence.${c}`) })))
const categoryChoices = computed(() => {
  const list = new Set(categories.value)
  if (form.value?.category) list.add(form.value.category)
  return [...list].map((c) => ({ value: c, label: c }))
})
const newCategory = ref('')
function addCategory() {
  const name = newCategory.value.trim()
  if (!name || !form.value) return
  if (!categories.value.includes(name)) categories.value = [...categories.value, name]
  form.value.category = name
  newCategory.value = ''
}
const amountText = (i: OpexItem) => (i.cost_type === 'variable' ? [i.variable_bp ? `${i.variable_bp / 100} %` : '', i.variable_fixed_minor ? `+ ${fmt(i.variable_fixed_minor)}` : ''].filter(Boolean).join(' ') || '–' : fmt(i.amount_minor))
const ended = (i: OpexItem) => !!i.end_on && i.end_on < today()
const rhythm = (i: OpexItem) => `${t(`own.opex.cadence.${i.cadence}`)}${i.annual_increase_pct ? ` · +${i.annual_increase_pct} %/${t('own.opex.yearShort')}` : ''}`
const span = (i: OpexItem) => (i.cadence === 'one_off' ? i.start_on : `${i.start_on} – ${i.end_on ?? t('own.opex.running')}`)

// ---- Costs Redesign (design project 9d0c2044, 'Costs Redesign.html'): summary strips, current month, scenario switch
const now = new Date()
const curCol = computed(() => (year.value === now.getFullYear() ? now.getMonth() : -1))
const isFixedRunning = (i: OpexItem) => i.cost_type !== 'variable' && i.start_on <= today() && (!i.end_on || i.end_on >= today())
/** What the running fixed lines cost in an average month (a quarter divided by 3, a year by 12; a one-off is not a run rate). */
const runRate = computed(() => Math.round(items.value.filter(isFixedRunning).reduce((a, i) => a + ({ monthly: 1, quarterly: 1 / 3, yearly: 1 / 12, one_off: 0 }[i.cadence] ?? 0) * i.amount_minor, 0)))
const next12 = ref<number | null>(null)
async function loadNext12() { try { next12.value = (await platform.opexForecast('base', 12)).total_cost } catch { next12.value = null } }
const dipsBelow = computed(() => {
  const f = forecast.value
  if (!f || !f.break_even) return ''
  const after = f.months.slice(f.months.findIndex((m) => m.month === f.break_even) + 1).find((m) => m.revenue < m.cost)
  return after ? t('own.opex.dipsBelow', { month: monthLabel(after.month) }) : t('own.opex.staysAbove')
})
const endsAt = computed(() => (forecast.value?.months.length ? t('own.opex.endsAt', { cash: money(forecast.value.months[forecast.value.months.length - 1]!.cash) }) : ''))
const maxCash = computed(() => Math.max(1, ...(forecast.value?.months.map((m) => m.cash) ?? [1])))
</script>

<template>
  <OcHead :title="t('own.opex.title')" :sub="t('own.opex.sub')">
    <label class="ox-cur">{{ t('own.opex.showIn') }}
      <select v-model="shown" class="ox-sel" data-testid="show-in"><option v-for="c in shownChoices" :key="c.value" :value="c.value">{{ c.label }}</option></select>
    </label>
    <button type="button" class="oc-btn" data-testid="new-cost" @click="openNew"><AppIcon name="plus" :size="14" />{{ t('own.opex.newCost') }}</button>
  </OcHead>

  <div v-if="shown !== 'USD'" class="ox-rates" data-testid="currency-bar">
    <button type="button" class="oc-btn oc-btn--g" data-testid="refresh-rates" @click="refreshRates"><AppIcon name="refresh" :size="14" />{{ t('own.opex.refreshRates') }}</button>
    <input v-model="typedRate" class="ox-inp" :aria-label="t('own.opex.rateFor', { code: shown })" :placeholder="t('own.opex.rateFor', { code: shown })" inputmode="decimal" autocomplete="off" />
    <button type="button" class="oc-btn oc-btn--g" @click="useTypedRate"><AppIcon name="refresh" :size="14" />{{ t('own.opex.rateSave') }}</button>
    <small class="oc-mut" data-testid="rate-note">{{ rateNote }}</small>
  </div>

  <AppTabs v-model="tab" class="oc-tabs" :tabs="tabs" :label="t('own.opex.tabsLabel')">
    <StateGate v-if="tab === 'costs'" :state="state" :rows="4" :empty-title="t('own.opex.emptyTitle')" :empty-text="t('own.opex.emptyText')" @retry="load">
      <div class="ox-kpis" data-testid="costs-kpis">
        <div class="ox-kpi ox-kpi--hl"><span class="ox-eyebrow">{{ t('own.opex.kRun') }}</span><b>{{ fmt(runRate) }}</b><small>{{ t('own.opex.kRunNote') }}</small></div>
        <div class="ox-kpi"><span class="ox-eyebrow">{{ t('own.opex.kYear', { year }) }}</span><b>{{ monthly ? fmt(monthly.total) : '–' }}</b><small>{{ t('own.opex.kLines', { n: items.length }) }}</small></div>
        <div class="ox-kpi"><span class="ox-eyebrow">{{ t('own.opex.kNext12') }}</span><b>{{ next12 === null ? '–' : fmt(next12) }}</b><small>{{ t('own.opex.kNext12Note') }}</small></div>
      </div>
      <div class="ox-tw">
        <table class="oc-tbl ox-tbl" data-testid="costs-table">
          <thead><tr><th>{{ t('own.opex.colName') }}</th><th>{{ t('own.opex.colCategory') }}</th><th class="ox-r">{{ t('own.opex.colAmount') }}</th><th>{{ t('own.opex.colRhythm') }}</th><th>{{ t('own.opex.colSpan') }}</th><th /></tr></thead>
          <tbody>
            <tr v-for="i in items" :key="i.id" :data-testid="`cost-${i.name}`">
              <td class="pri" :data-label="t('own.opex.colName')"><b>{{ i.name }}</b><small v-if="i.vendor || i.note" class="oc-mut" style="display: block">{{ [i.vendor, i.note].filter(Boolean).join(' · ') }}</small></td>
              <td :data-label="t('own.opex.colCategory')">{{ i.category }}</td>
              <td class="ox-r" :data-label="t('own.opex.colAmount')">{{ amountText(i) }}</td>
              <td :data-label="t('own.opex.colRhythm')">{{ i.cost_type === 'variable' ? t('own.opex.variableTag') : rhythm(i) }}</td>
              <td class="oc-mut" :data-label="t('own.opex.colSpan')">{{ span(i) }} <OcPill v-if="ended(i)" tone="warn">{{ t('own.opex.ended') }}</OcPill><span v-else-if="!i.end_on && i.cadence !== 'one_off'" class="ox-live" /></td>
              <td>
                <div class="ox-act">
                  <button type="button" class="ox-btn" @click="openEdit(i)"><AppIcon name="edit" :size="14" />{{ t('own.opex.edit') }}</button>
                  <button type="button" class="ox-btn ox-btn--dng" @click="removing = i"><AppIcon name="trash" :size="14" />{{ t('own.opex.remove') }}</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </StateGate>

    <div v-else-if="tab === 'forecast'" data-testid="forecast">
      <p class="ox-lead">{{ t('own.opex.fcSub') }}</p>
      <div class="ox-bar">
        <div class="ox-seg" role="group" :aria-label="t('own.opex.tabForecast')" data-testid="scenario">
          <button v-for="c in scenarioChoices" :key="c.id" type="button" :class="{ on: scenario === c.id }" :aria-pressed="scenario === c.id" @click="scenario = c.id as OpexScenarioName">{{ c.label }}</button>
        </div>
        <label class="ox-cur">{{ t('own.opex.horizon') }}
          <select v-model="horizon" class="ox-sel" data-testid="horizon"><option v-for="c in horizonChoices" :key="c.value" :value="c.value">{{ c.label }}</option></select>
        </label>
      </div>
      <AppAlert v-if="forecastError" tone="danger" role="alert">{{ forecastError }}</AppAlert>
      <template v-else-if="forecast">
        <div class="ox-kpis">
          <div class="ox-kpi"><span class="ox-eyebrow">{{ t('own.opex.renewing') }}</span><b data-testid="fc-renewing">{{ fmt(forecast.renewing_monthly) }}</b><small>{{ t('own.opex.renewingNote', { count: forecast.paying_squares }) }}</small></div>
          <div class="ox-kpi ox-kpi--hl"><span class="ox-eyebrow">{{ t('own.opex.breakEven') }}</span><b data-testid="fc-even">{{ forecast.break_even ? monthLabel(forecast.break_even) : t('own.opex.breakEvenNone') }}</b><small>{{ dipsBelow }}</small></div>
          <div class="ox-kpi"><span class="ox-eyebrow">{{ t('own.opex.runway') }}</span><b data-testid="fc-runway">{{ forecast.runway_months === null ? t('own.opex.runwayNone') : t('own.opex.runwayMonths', { n: forecast.runway_months }) }}</b><small>{{ endsAt }}</small></div>
        </div>
        <div class="ox-tw">
          <table class="oc-tbl ox-tbl" data-testid="fc-table">
            <thead><tr><th>{{ t('own.opex.colMonth') }}</th><th class="ox-r">{{ t('own.opex.colRevenue') }}</th><th class="ox-r">{{ t('own.opex.colCost') }}</th><th class="ox-r">{{ t('own.opex.colNet') }}</th><th class="ox-r">{{ t('own.opex.colCash') }}</th><th /></tr></thead>
            <tbody>
              <tr v-for="m in forecast.months" :key="m.month">
                <td class="pri"><b>{{ monthLabel(m.month) }}</b></td>
                <td class="ox-r">{{ cell(m.revenue) }}</td><td class="ox-r">{{ cell(m.cost) }}</td>
                <td class="ox-r" :class="{ 'ox-neg': m.net < 0 }">{{ money(m.net) }}</td>
                <td class="ox-r" :class="{ 'ox-neg': m.cash < 0 }">{{ money(m.cash) }}</td>
                <td><div class="ox-meter" aria-hidden="true"><i :style="{ width: `${Math.max(0, Math.min(100, (m.cash / maxCash) * 100))}%` }" /></div></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="forecast.actuals.some((a) => a.revenue)" class="ox-lead" style="margin: 12px 0 0">{{ t('own.opex.actualHead') }}: {{ forecast.actuals.map((a) => `${monthLabel(a.month)} ${fmt(a.revenue)}`).join(' · ') }}</p>
      </template>
      <section v-if="assume" class="ox-card ox-card--wide" data-testid="assumptions">
        <div class="ox-ahead">
          <div><h3>{{ t('own.opex.assumptions') }}</h3><p class="oc-mut" style="margin: 4px 0 0; font-size: var(--text-sm)">{{ t('own.opex.assumptionsSub') }}</p></div>
          <AppField v-model="assume.cash" :label="t('own.opex.fCash')" suffix="USD" inputmode="decimal" style="width: 230px" />
        </div>
        <div class="ox-ass">
          <div v-for="n in scenarioNames" :key="n" class="ox-card" :class="{ 'ox-card--on': scenario === n }">
            <h3>{{ scenarioLabel(n) }}</h3>
            <AppField v-model="assume.rows[n].add" :label="t('own.opex.fNew')" inputmode="decimal" />
            <AppField v-model="assume.rows[n].churn" :label="t('own.opex.fChurn')" suffix="%" inputmode="decimal" />
            <AppField v-model="assume.rows[n].arpu" :label="t('own.opex.fArpu')" suffix="USD" inputmode="decimal" optional />
          </div>
        </div>
        <AppAlert v-if="assumeError" tone="danger" role="alert">{{ assumeError }}</AppAlert>
        <div class="ox-foot">
          <span class="oc-mut" style="font-size: var(--text-xs)">{{ t('own.opex.assumeNote') }}</span>
          <button type="button" class="oc-btn" :disabled="busy" data-testid="save-assumptions" @click="saveAssumptions"><AppIcon name="check" :size="14" />{{ t('own.opex.saveAssumptions') }}</button>
        </div>
      </section>
    </div>

    <section v-else data-testid="monthly">
      <div class="ox-tw">
        <div class="ox-tb">
          <div class="ox-yr">
            <button type="button" class="ox-btn" :aria-label="t('own.opex.prevYear')" @click="year -= 1">‹</button>
            <b data-testid="year">{{ year }}</b>
            <button type="button" class="ox-btn" :aria-label="t('own.opex.nextYear')" @click="year += 1">›</button>
          </div>
          <div class="ox-act">
            <button type="button" class="ox-btn" data-testid="record-real" :disabled="!fixedChoices.length" @click="openReal"><AppIcon name="plus" :size="14" />{{ t('own.opex.recordReal') }}</button>
            <button type="button" class="ox-btn" data-testid="export" @click="downloadCsv"><AppIcon name="download" :size="14" />{{ t('own.opex.download') }}</button>
          </div>
        </div>
        <AppAlert v-if="monthlyError" tone="danger" role="alert" style="margin: 12px">{{ monthlyError }}</AppAlert>
        <p v-else-if="!monthly || !monthly.categories.length" class="oc-mut" style="margin: 12px">{{ t('own.opex.noMonthly') }}</p>
        <table v-else class="oc-tbl ox-tbl ox-grid" data-testid="grid">
          <thead><tr><th>{{ t('own.opex.colCategory') }}</th><th v-for="(m, idx) in months" :key="m" :class="{ 'ox-cm': idx === curCol }">{{ m }}</th><th>{{ t('own.opex.total') }}</th></tr></thead>
          <tbody>
            <tr v-for="c in monthly.categories" :key="c.name">
              <td class="pri"><b>{{ c.name }}</b></td>
              <td v-for="(v, idx) in c.months" :key="idx" :class="{ 'ox-cm': idx === curCol, 'ox-z': !v }">{{ cell(v) }}</td>
              <td>{{ fmt(c.total) }}</td>
            </tr>
            <tr class="ox-sum">
              <td class="pri">{{ t('own.opex.total') }}</td>
              <td v-for="(v, idx) in monthly.totals" :key="idx" :class="{ 'ox-cm': idx === curCol, 'ox-z': !v }">{{ cell(v) }}</td>
              <td data-testid="year-total">{{ fmt(monthly.total) }}</td>
            </tr>
            <template v-if="differs">
              <tr class="oc-mut" data-testid="plan-row">
                <td class="pri">{{ t('own.opex.planRow') }}</td>
                <td v-for="(v, idx) in monthly.planned_totals" :key="idx">{{ cell(v) }}</td>
                <td>{{ fmt(monthly.planned_totals.reduce((a, b) => a + b, 0)) }}</td>
              </tr>
              <tr class="oc-mut">
                <td class="pri">{{ t('own.opex.diffRow') }}</td>
                <td v-for="(v, idx) in monthly.totals" :key="idx">{{ v === monthly.planned_totals[idx] ? '–' : money(v - monthly.planned_totals[idx]!) }}</td>
                <td />
              </tr>
            </template>
          </tbody>
        </table>
      </div>
      <small v-if="change" class="oc-mut" style="display: block; margin-top: 8px">{{ change }}</small>
      <div v-if="actuals.length" style="margin-top: 16px" data-testid="real-list">
        <b>{{ t('own.opex.realList') }}</b>
        <ul style="list-style: none; padding: 0; margin: 8px 0 0">
          <li v-for="a in actuals" :key="a.id" style="display: flex; gap: 12px; align-items: center; padding: 4px 0">
            <span>{{ a.item_name }} · {{ monthLabel(a.month) }} · {{ fmt(a.amount_minor) }}</span>
            <button type="button" class="ox-btn" @click="removeReal(a)"><AppIcon name="trash" :size="14" />{{ t('own.opex.remove') }}</button>
          </li>
        </ul>
      </div>
    </section>
  </AppTabs>

  <ConfirmDialog v-if="form" :title="t(form.id ? 'own.opex.editCost' : 'own.opex.newCost')" :verb="t('own.opex.save')" tone="primary" wide :confirm-disabled="busy" @confirm="save" @cancel="form = null">
    <div class="vo-form">
      <AppField v-model="form.name" :label="t('own.opex.fName')" autocomplete="off" />
      <AppField v-model="form.category" as="select" :label="t('own.opex.fCategory')" :options="categoryChoices" />
      <div class="vo-full" style="display: flex; gap: 8px; align-items: flex-end">
        <AppField v-model="newCategory" :label="t('own.opex.fNewCategory')" optional autocomplete="off" />
        <button type="button" class="oc-btn oc-btn--g" data-testid="add-category" @click="addCategory"><AppIcon name="plus" :size="14" />{{ t('own.opex.addCategory') }}</button>
      </div>
      <AppField v-model="form.kind" as="select" :label="t('own.opex.fType')" :options="kindChoices" />
      <template v-if="form.kind === 'variable'">
        <AppField v-model="form.share" :label="t('own.opex.fShare')" suffix="%" :hint="t('own.opex.fShareHint')" inputmode="decimal" />
        <AppField v-model="form.perOrder" :label="t('own.opex.fPerOrder')" suffix="USD" inputmode="decimal" />
        <p class="oc-mut vo-full" style="margin: 0">{{ t('own.opex.variableNote') }}</p>
      </template>
      <template v-else>
        <AppField v-model="form.amount" :label="t('own.opex.fAmount')" suffix="USD" inputmode="decimal" />
        <AppField v-model="form.cadence" as="select" :label="t('own.opex.fCadence')" :options="cadenceChoices" />
      </template>
      <AppField v-model="form.start_on" type="date" :label="t('own.opex.fStart')" />
      <AppField v-if="form.kind === 'variable' || form.cadence !== 'one_off'" v-model="form.end_on" type="date" :label="t('own.opex.fEnd')" :hint="t('own.opex.fEndHint')" optional />
      <AppField v-if="form.kind === 'fixed' && form.cadence !== 'one_off'" v-model="form.pct" :label="t('own.opex.fRise')" suffix="%" :hint="t('own.opex.fRiseHint')" inputmode="numeric" />
      <AppField v-model="form.vendor" :label="t('own.opex.fVendor')" optional />
      <AppField class="vo-full" v-model="form.note" :label="t('own.opex.fNote')" optional />
    </div>
    <AppAlert v-if="formError" tone="danger" role="alert">{{ formError }}</AppAlert>
  </ConfirmDialog>

  <ConfirmDialog v-if="real" :title="t('own.opex.recordTitle')" :verb="t('own.opex.save')" tone="primary" :confirm-disabled="busy" @confirm="saveReal" @cancel="real = null">
    <p>{{ t('own.opex.recordText') }}</p>
    <div class="vo-form">
      <AppField v-model="real.item_id" as="select" :label="t('own.opex.fLine')" :options="fixedChoices" />
      <AppField v-model="real.month" type="month" :label="t('own.opex.fMonth')" />
      <AppField v-model="real.amount" :label="t('own.opex.fReal')" suffix="USD" inputmode="decimal" />
    </div>
    <AppAlert v-if="realError" tone="danger" role="alert">{{ realError }}</AppAlert>
  </ConfirmDialog>

  <ConfirmDialog v-if="removing" :title="t('own.opex.removeTitle', { name: removing.name })" :verb="t('own.opex.remove')" icon="trash" tone="danger" @confirm="remove" @cancel="removing = null">
    <p>{{ t('own.opex.removeText') }}</p>
  </ConfirmDialog>
</template>

<style scoped>
.ox-cur { display: inline-flex; align-items: center; gap: 8px; font-size: var(--text-sm); color: var(--color-text-muted) }
.ox-sel, .ox-inp { font: 500 var(--text-sm) var(--font-sans); min-height: 34px; border: 1px solid var(--color-border-strong); background: var(--color-surface); color: var(--color-text); border-radius: var(--shape-field); padding: 0 10px }
.ox-sel:hover { border-color: var(--color-brass) }
.ox-inp { font-weight: 400; width: 170px }
.ox-sel:focus-visible, .ox-inp:focus-visible { outline: 0; border-color: var(--color-brass); box-shadow: var(--focus-ring) }
.ox-rates { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 12px 0 0 }
.ox-btn { font: 500 var(--text-xs) var(--font-sans); min-height: 30px; padding: 0 14px; border: 1px solid var(--color-border-strong); background: transparent; color: var(--color-text); border-radius: var(--shape-control); cursor: pointer }
.ox-btn:hover:not(:disabled) { border-color: var(--color-brass) }
.ox-btn:disabled { opacity: .5; cursor: not-allowed }
.ox-btn--dng:hover { color: var(--color-danger); border-color: var(--color-danger) }
.ox-btn:focus-visible { outline: 0; box-shadow: var(--focus-ring) }
.ox-act { display: flex; gap: 6px; justify-content: flex-end; align-items: center }
@media (max-width: 700px) { .oc-tbl td:has(.ox-act) { grid-column: 1 / -1; } .oc-tbl td .ox-act { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 100%; } .oc-tbl td .ox-act .ox-btn { width: 100%; } } /* the Edit and Delete buttons of a cost card: two equal buttons side by side (W25-R43) */
.ox-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); margin: 20px 0 }
.ox-kpi { padding: 16px 20px; border-right: 1px solid var(--color-border) }
.ox-kpi:last-child { border-right: 0 }
.ox-eyebrow { font: 500 .72rem/1 var(--font-sans); letter-spacing: .12em; text-transform: uppercase; color: var(--color-text-muted) }
.ox-kpi--hl .ox-eyebrow { color: var(--color-brass-text) }
.ox-kpi b { display: block; font: 600 1.6rem/1.2 var(--font-heading); letter-spacing: -.015em; margin-top: 8px }
.ox-kpi small { color: var(--color-text-muted); font-size: var(--text-xs) }
.ox-tw { border: 1px solid var(--color-border); border-radius: var(--shape-inner); background: var(--color-surface); overflow: auto }
.ox-tbl { font-variant-numeric: tabular-nums }
.ox-tbl tbody tr:last-child td { border-bottom: 0 }
.ox-tbl tbody tr:hover { background: var(--color-accent-subtle) }
.ox-r { text-align: right !important }
.ox-neg { color: var(--color-danger); font-weight: 500 }
.ox-live { display: inline-flex; align-items: center; gap: 6px }
.ox-live::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--color-success) }
.ox-tb { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 12px; border-bottom: 1px solid var(--color-border); flex-wrap: wrap }
.ox-yr { display: flex; align-items: center; gap: 8px; font: 600 1.05rem var(--font-heading) }
.ox-grid th, .ox-grid td { text-align: right }
.ox-grid th:first-child, .ox-grid td:first-child { text-align: left }
.ox-grid td:last-child { font-weight: 600 }
.ox-grid .ox-cm { background: var(--color-brass-subtle) }
.ox-grid th.ox-cm { color: var(--color-brass-text) }
.ox-grid .ox-z { color: var(--color-border-strong) }
.ox-grid .ox-sum td { font-weight: 600; background: var(--color-surface-sunken); border-top: 1px solid var(--color-border-strong) }
.ox-lead { color: var(--color-text-muted); font-size: var(--text-sm); margin: 16px 0; max-width: 70ch }
.ox-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap }
.ox-seg { display: inline-flex; border: 1px solid var(--color-border-strong); border-radius: var(--shape-control); overflow: hidden }
.ox-seg button { background: none; border: 0; border-right: 1px solid var(--color-border); min-height: 32px; padding: 0 16px; font: 400 var(--text-sm) var(--font-sans); color: var(--color-text-muted); cursor: pointer }
.ox-seg button:last-child { border-right: 0 }
.ox-seg button.on { background: var(--color-primary); color: var(--color-on-primary); font-weight: 600 }
.ox-seg button:focus-visible { outline: 0; box-shadow: inset var(--focus-ring) }
.ox-meter { height: 4px; background: var(--color-border); border-radius: 2px; width: 96px }
.ox-meter i { display: block; height: 100%; background: var(--color-brass); border-radius: 2px }
.ox-card { border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); padding: 18px; display: grid; gap: 14px; align-content: start }
.ox-card--on { border-color: var(--color-brass) }
.ox-card--wide { display: block; margin-top: 20px; padding: 22px }
.ox-card h3, .ox-ahead h3 { font: 600 var(--text-lg) var(--font-heading); letter-spacing: -.015em; margin: 0 }
.ox-ahead { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: flex-end }
.ox-ass { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 20px; padding-bottom: 2px }
.ox-foot { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-top: 20px; flex-wrap: wrap }
.vo-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px 20px; max-height: 64vh; overflow: auto; padding: 10px 12px 10px 10px; margin: 0 -4px; align-items: start }
.vo-full { grid-column: 1 / -1 }
</style>
