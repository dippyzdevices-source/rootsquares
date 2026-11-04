<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { errorText } from '@/errorText'
import { usd } from '@rootsquares/ui/mock/pricing'
import { type PlatformSquare } from '@rootsquares/ui/types/platformTypes'
import { adminApi as platform } from '@/adminApi'
import PackageBuilder from './PackageBuilder.vue'
import { buildGraph, stepOf, type PkgNode } from './packageGraph'

// Owner console, one square, Package tab (W19-R20, R23, R25, ADR 082): a platform admin agrees a custom package with this square: the always-on parts and the
// modules (a hierarchy, drawn by PackageBuilder in five views) and ONE amount per period. Nothing is for sale here (the Pricing page only says "speak to us").
// The square owner then pays the agreed amount like any plan. The Event pass is fixed: no custom package for it.
const props = defineProps<{ square: PlatformSquare; prospectId?: string }>()
const emit = defineEmits<{ saved: [sq: PlatformSquare] }>()
const { t } = useI18n()
const { push } = useToast()
const nodes = ref<PkgNode[]>([])
const chosen = ref<string[]>([])
const amount = ref('')
const interval = ref<'month' | 'year'>('month')
const busy = ref(false)
const error = ref('')
const isEvent = computed(() => props.square.launch_package === 'event' || props.square.running_plan === 'event')
const isCustom = computed(() => props.square.launch_package === 'custom')
const minor = computed(() => Math.round(parseFloat(amount.value.replace(',', '.')) * 100))
const guide = ref<number[]>([0, 0, 0, 0, 0])
// The guide for what is chosen: the highest guiding minimum among the steps it reaches (per month; a yearly amount is compared as a twelfth)
const reached = computed(() => { const g = buildGraph(nodes.value); return Math.max(0, ...chosen.value.filter((id) => g.info[id]).map((id) => stepOf(g, id))) })
const minGuide = computed(() => Math.max(0, ...guide.value.slice(0, reached.value + 1)))
const perMonth = computed(() => (interval.value === 'year' ? minor.value / 12 : minor.value))
const belowGuide = computed(() => minGuide.value > 0 && Number.isFinite(perMonth.value) && perMonth.value < minGuide.value)
const valid = computed(() => () => Number.isFinite(minor.value) && minor.value >= 100 && chosen.value.length > 0)

function fill() {
  const s = props.square
  const everyCore = nodes.value.filter((n) => n.core).map((n) => n.id)
  chosen.value = isCustom.value ? [...s.allowed_modules, ...(s.core_modules ?? everyCore)] : [...(s.modules ?? []), ...(s.core_modules ?? everyCore)]
  amount.value = isCustom.value && s.custom_amount_minor ? (s.custom_amount_minor / 100).toFixed(2).replace(/\.00$/, '') : ''
  interval.value = s.custom_interval === 'year' ? 'year' : 'month'
}
async function save() {
  busy.value = true
  error.value = ''
  try {
    const next = await platform.setCustomPackage(props.square.id, { modules: chosen.value, amount_minor: minor.value, interval: interval.value })
    emit('saved', next)
    if (props.prospectId) await platform.updateProspect(props.prospectId, { status: 'won' }).catch(() => undefined) // the request that led here is now agreed
    push(t('own.custom.saved'), 'success')
  } catch (e) { error.value = errorText(t, e) } finally { busy.value = false }
}
onMounted(async () => {
  try {
    const all = await platform.moduleCatalogue()
    nodes.value = [
      ...all.core.map((c) => ({ id: c.key, name: c.label, desc: c.description, needs: c.needs, core: true })),
      ...all.items.map((m) => ({ id: m.key, name: m.label, desc: m.description, needs: [...m.needs, ...(all.module_core_needs[m.key] ?? [])], core: false })),
    ]
  } catch (e) { error.value = errorText(t, e) }
  try { guide.value = await platform.customGuide() } catch { /* no guide shown */ }
  fill()
})
watch(() => props.square.id, fill)
</script>

<template>
  <section class="oc-card" data-testid="custom-package">
    <h3 class="oc-h3">{{ t('own.custom.title') }}</h3>
    <div class="cp-body">
      <AppAlert v-if="prospectId" tone="info">{{ t('own.custom.fromProspect') }}</AppAlert>
      <p class="oc-mut cp-lede">{{ t(isEvent ? 'own.custom.eventFixed' : isCustom ? 'own.custom.ledeOn' : 'own.custom.lede') }}</p>
      <template v-if="!isEvent">
        <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
        <div class="cp-grid">
          <AppField v-model="amount" :label="t('own.custom.amount')" :hint="t('own.custom.amountHint')" suffix="USD" placeholder="0" />
          <AppField v-model="interval" as="select" :label="t('own.custom.interval')" :options="[{ value: 'month', label: t('marketing.pricing.monthly') }, { value: 'year', label: t('marketing.pricing.yearly') }]" />
          <div v-if="minGuide" class="cp-guide" :class="{ low: belowGuide }" data-testid="custom-guide-line">
            <b>{{ t('own.custom.guideLine', { amount: usd(minGuide), n: reached + 1 }) }}</b>
            <small>{{ t(belowGuide ? 'own.custom.guideLow' : 'own.custom.guideOk') }}</small>
          </div>
        </div>
        <PackageBuilder v-if="nodes.length" v-model="chosen" :nodes="nodes" :guide="guide" />
        <div class="cp-foot">
          <p class="oc-mut cp-note">{{ t('own.custom.note') }}</p>
          <AppButton icon="plus" :loading="busy" :disabled="!valid" @click="save">{{ t(isCustom ? 'own.custom.update' : 'own.custom.make') }}</AppButton>
        </div>
      </template>
    </div>
  </section>
</template>

<style scoped>
.cp-body { display: grid; gap: 12px; padding: 14px 18px; min-width: 0; }
.cp-lede, .cp-note { margin: 0; font-size: var(--text-sm); }
.cp-grid { display: grid; grid-template-columns: minmax(180px, 240px) minmax(150px, 200px) minmax(0, 1fr); gap: 12px 20px; align-items: start; }
.cp-guide { display: grid; gap: 2px; align-content: center; min-height: 44px; margin-top: 24px; padding: 8px 12px; border: 1px solid var(--color-border); border-left: 3px solid var(--color-brass); border-radius: var(--shape-surface); background: var(--color-surface); font-size: var(--text-sm); }
.cp-guide small { color: var(--color-text-muted); }
.cp-guide.low { border-color: var(--color-warn, var(--color-brass)); background: color-mix(in srgb, var(--color-brass) 14%, var(--color-surface)); }
.cp-guide.low small { color: var(--color-text); }
@media (max-width: 760px) { .cp-grid { grid-template-columns: minmax(0, 1fr); } .cp-guide { margin-top: 0; } }
.cp-foot { display: flex; flex-wrap: wrap; gap: 12px 20px; align-items: center; justify-content: space-between; }
</style>
