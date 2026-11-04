<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import OcHead from '@/components/OcHead.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import OwnerCustomGuide from './OwnerCustomGuide.vue'
import OwnerInvoiceDetails from './OwnerInvoiceDetails.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { errorText } from '@/errorText'
import { usd } from '@rootsquares/ui/mock/pricing'
import { type PlanPrice } from '@rootsquares/ui/types/platformTypes'
import { adminApi as platform } from '@/adminApi'

// Owner console, Prices (W14-R27, docs/reference/prices-and-vouchers.md): every price the platform charges is data in `plan_prices` and is changed here, with no code change.
// A change applies to new orders only; an order already made and a subscription that already renews keep their price. Each change is audit-logged.
const { t } = useI18n()
const { push } = useToast()
const rows = ref<PlanPrice[]>([])
const loading = ref(true)
const error = ref('')
const typed = ref<Record<string, string>>({})
const busy = ref<string | null>(null)
const bad = ref<Record<string, boolean>>({})

const GROUPS = [
  { id: 'launch', keys: ['launch.roots', 'launch.square', 'launch.grove'] },
  { id: 'running', keys: ['running.live.month', 'running.live.year', 'running.keep.month', 'running.keep.year'] },
  { id: 'event', keys: ['launch.event'] },
]
const byKey = computed(() => Object.fromEntries(rows.value.map((r) => [r.key, r])))
// every price the platform knows is listed, set or not: an unset price has no amount and cannot be charged until it is set here
interface Row { key: string; amount_minor: number | null }
const groups = computed(() => GROUPS.map((g) => ({ ...g, items: g.keys.map((k): Row => ({ key: k, amount_minor: byKey.value[k]?.amount_minor ?? null })) })))
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : 'default'))

const dollars = (minor: number) => (minor / 100).toFixed(2).replace(/\.00$/, '')
function fill() { typed.value = Object.fromEntries(rows.value.map((r) => [r.key, dollars(r.amount_minor)])) }
async function load() {
  loading.value = true
  try { rows.value = await platform.getPrices(); error.value = ''; fill() } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}
onMounted(load)

/** "24.50" or "25" in dollars to cents; null when it is not a plain amount. */
function toMinor(text: string): number | null {
  const m = /^\s*(\d{1,6})(?:[.,](\d{1,2}))?\s*$/.exec(text)
  if (!m) return null
  return Number(m[1]) * 100 + Number((m[2] ?? '').padEnd(2, '0') || 0)
}
const changed = (r: Row) => toMinor(typed.value[r.key] ?? '') !== null && toMinor(typed.value[r.key] ?? '') !== r.amount_minor

async function save(r: Row) {
  const minor = toMinor(typed.value[r.key] ?? '')
  bad.value = { ...bad.value, [r.key]: minor === null }
  if (minor === null) return
  busy.value = r.key
  try {
    const saved = await platform.setPrice(r.key, minor)
    rows.value = rows.value.some((x) => x.key === saved.key) ? rows.value.map((x) => (x.key === saved.key ? saved : x)) : [...rows.value, saved]
    typed.value[r.key] = dollars(saved.amount_minor)
    push(t('own.prices.saved'), 'success')
  } catch (e) { push(errorText(t, e), 'danger') } finally { busy.value = null }
}
const label = (key: string) => t(`own.prices.k.${key.replace(/\./g, '_')}`)
</script>

<template>
  <OcHead :title="t('own.prices.title')" :sub="t('own.prices.sub')" />
  <AppAlert tone="info" style="margin-top: 14px">{{ t('own.prices.note') }}</AppAlert>
  <StateGate :state="state" :rows="6" :empty-title="t('own.prices.emptyTitle')" :empty-text="t('own.prices.emptyText')" @retry="load">
    <section v-for="g in groups" :key="g.id" class="oc-card" style="margin-top: 14px" :data-testid="`prices-${g.id}`">
      <h3 class="oc-h3">{{ t(`own.prices.g.${g.id}`) }}</h3>
      <div v-for="r in g.items" :key="r.key" class="oc-li" style="align-items: center; gap: 12px; flex-wrap: wrap">
        <div style="flex: 1; min-width: 160px">
          <b>{{ label(r.key) }}</b>
          <small class="oc-mut" style="display: block">{{ r.amount_minor === null ? t('own.prices.notSet') : t('own.prices.now', { price: usd(r.amount_minor) }) }}</small>
        </div>
        <label class="oc-fld" style="width: 150px">
          <span aria-hidden="true">$</span>
          <input
            v-model="typed[r.key]" class="price-input" inputmode="decimal" :aria-label="label(r.key)" :aria-invalid="bad[r.key] || undefined" 
            @keyup.enter="save(r)"
          >
        </label>
        <button type="button" class="oc-btn price-save" :disabled="busy === r.key || !changed(r)" @click="save(r)"><AppIcon name="check" :size="14" />{{ t('own.prices.save') }}</button>
        <span v-if="bad[r.key]" class="oc-mut" style="flex-basis: 100%; color: var(--color-danger)">{{ t('own.prices.invalid') }}</span>
      </div>
    </section>
  </StateGate>
  <OwnerInvoiceDetails />
  <OwnerCustomGuide />
</template>

<style scoped>
/* On a phone the Save button drops under the price box and takes its place: the same width, at the same right edge (W25-R44). */
@media (max-width: 700px) { .price-save { margin-left: auto; width: 150px; } }
</style>
