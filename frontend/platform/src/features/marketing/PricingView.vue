<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { startTarget } from '@/features/platform/startFlow'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import FaqSection from './components/FaqSection.vue'
import { MOCK_MODULES, allowedModules } from '@/services/modulesCatalogue'
import { loadTaxRates, taxRates } from '@/services/taxRates'
import CustomRequestCard from './components/CustomRequestCard.vue'
import { EVENT_PASS_DAYS, LAUNCH_PACKAGES, RUNNING_PLANS, usd, type LaunchPackage, type RunningPlan } from '@rootsquares/ui/mock/pricing'
import { loadPrices, minorOf, pricesState } from '@/services/prices'

// Pricing (docs/plans/pricing-strategy.md, W10-R39): two parts. 1) The launch package, paid once: Roots (the always-on parts), Square (+ Recommended modules), Grove (+ Good to have).
// 2) The running plan: Keep (saved, asleep), Live (always on), Event pass (one event, one-off); Monthly / Yearly switch for Keep and Live. The module names come from the
// module catalogue so they never go stale; amounts are provisional data (mock/pricing.ts), USD only. Same .bp-* classes as design v4 (ext2.css).
const { t } = useI18n()
const router = useRouter()

const yearly = ref(false)
const loading = ref(true)
const failed = ref(false)
// Prices are data on the platform (GET /prices, a platform admin sets them on the owner console): nothing is written in the code. A price that is not set shows a dash.
async function load() {
  loading.value = true
  failed.value = false
  await loadPrices(true)
  failed.value = pricesState.value === 'failed'
  loading.value = false
}
onMounted(load)

const CORE = ['home', 'about', 'contact', 'login', 'legal', 'settings', 'media', 'admin', 'account']
const coreNames = computed(() => CORE.map((k) => t(`plat.modules.coreItems.${k}.name`)).join(', '))
// Square lists what it includes; Grove lists what it adds on top (docs/reference/packages-and-features.md)
const squareKeys = allowedModules(MOCK_MODULES, 'square')
const names = (pkg: string) => MOCK_MODULES.filter((m) => (pkg === 'square' ? squareKeys.includes(m.key) : !squareKeys.includes(m.key))).map((m) => m.label).join(', ')
const features = (p: LaunchPackage) => [1, 2, 3].map((i) => t(`marketing.pricing.launch.${p.id}.f${i}`, { core: coreNames.value, modules: names(p.id) }))
const runningFeatures = (p: RunningPlan) => [1, 2, 3, 4].map((i) => t(`marketing.pricing.running.${p.id}.f${i}`, { days: EVENT_PASS_DAYS }))
const launchMinor = (p: LaunchPackage) => minorOf(`launch.${p.id}`)
const runningMinor = (p: RunningPlan) => minorOf(p.id === 'event' ? 'launch.event' : `running.${p.id}.${yearly.value ? 'year' : 'month'}`)
const amount = (minor: number | null) => (minor === null ? '—' : usd(minor))
loadTaxRates()
const regionName = new Intl.DisplayNames(['en'], { type: 'region' })
const runningAmount = (p: RunningPlan) => amount(runningMinor(p))
const runningUnit = (p: RunningPlan) => (p.id === 'event' ? t('marketing.pricing.perEvent') : yearly.value ? t('marketing.pricing.perYear') : t('marketing.pricing.perMonth'))

// Create square is the real flow; /start is the clickable prototype and creates nothing (W12-R21). Live and Keep are plans of an existing square, so they only open sign up.
const auth = useAuthStore()
function startLaunch(p: LaunchPackage) { void router.push(startTarget(!!auth.user, { package: p.id })) }
function startRunning(p: RunningPlan) { void router.push(startTarget(!!auth.user, p.id === 'event' ? { running: 'event' } : {})) }
</script>

<template>
  <section class="bp-hero">
    <span class="rs-eyebrow">{{ t('marketing.pricing.eyebrow') }}</span>
    <h1>{{ t('marketing.pricing.title') }} <em>{{ t('marketing.pricing.titleEm') }}</em></h1>
    <p class="bs-mute" style="margin: 0; max-width: 56ch">{{ t('marketing.pricing.lede') }}</p>
    <p class="pr-taxline" data-testid="pricing-tax" style="margin: 8px 0 0; max-width: 56ch; font-size: var(--text-sm)"><b>{{ t('marketing.pricing.taxLine') }}</b><template v-for="[c, pct] in Object.entries(taxRates)" :key="c"> {{ t('tax.pricingNote', { country: regionName.of(c) ?? c, percent: pct }) }}</template></p>
  </section>

  <div v-if="failed" style="padding: 0 var(--page-x)">
    <AppAlert tone="danger" :title="t('marketing.pricing.errorTitle')">
      {{ t('marketing.pricing.errorText') }}
      <template #action><AppButton variant="secondary" size="sm" @click="load">{{ t('marketing.pricing.reload') }}</AppButton></template>
    </AppAlert>
  </div>
  <template v-else>
    <section class="pr-head">
      <span class="rs-eyebrow">{{ t('marketing.pricing.launchEyebrow') }}</span>
      <h2>{{ t('marketing.pricing.launchTitle') }}</h2>
      <p class="bs-mute">{{ t('marketing.pricing.launchLede') }}</p>
    </section>
    <div class="bp-plans" :aria-busy="loading || undefined">
      <article v-for="p in LAUNCH_PACKAGES" :key="p.id" class="bp-plan" :class="p.highlighted && 'bp-plan--hl'">
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px">
          <h3 style="font-weight: 500; font-size: var(--text-lg); margin: 0">{{ t(`marketing.pricing.launch.${p.id}.name`) }}</h3>
          <span v-if="p.highlighted" class="rs-chip rs-chip--info">{{ t('marketing.pricing.badge') }}</span>
        </div>
        <span class="bs-mute" style="font-size: var(--text-sm)">{{ t(`marketing.pricing.launch.${p.id}.text`) }}</span>
        <div class="bp-price">{{ amount(launchMinor(p)) }}<small> {{ t('marketing.pricing.oneOff') }}</small></div>
        <AppButton block size="lg" :variant="p.highlighted ? 'primary' : 'secondary'" style="min-height: 44px" @click="startLaunch(p)">{{ t(`marketing.pricing.launch.${p.id}.cta`) }}</AppButton>
        <ul class="bp-ft"><li v-for="f in features(p)" :key="f"><AppIcon name="check" :size="14" />{{ f }}</li></ul>
      </article>
    </div>

    <section class="pr-head">
      <span class="rs-eyebrow">{{ t('marketing.pricing.runningEyebrow') }}</span>
      <h2>{{ t('marketing.pricing.runningTitle') }}</h2>
      <p class="bs-mute">{{ t('marketing.pricing.runningLede') }}</p>
      <div class="bp-tog" role="group" :aria-label="t('marketing.pricing.period')">
        <button type="button" :aria-pressed="!yearly" @click="yearly = false">{{ t('marketing.pricing.monthly') }}</button>
        <button type="button" :aria-pressed="yearly" @click="yearly = true">{{ t('marketing.pricing.yearly') }} <span style="font-size: 0.7rem; opacity: 0.85">{{ t('marketing.pricing.save') }}</span></button>
      </div>
    </section>
    <div class="bp-plans">
      <article v-for="p in RUNNING_PLANS" :key="p.id" class="bp-plan" :class="p.highlighted && 'bp-plan--hl'">
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px">
          <h3 style="font-weight: 500; font-size: var(--text-lg); margin: 0">{{ t(`marketing.pricing.running.${p.id}.name`) }}</h3>
          <span v-if="p.highlighted" class="rs-chip rs-chip--info">{{ t('marketing.pricing.badge') }}</span>
        </div>
        <span class="bs-mute" style="font-size: var(--text-sm)">{{ t(`marketing.pricing.running.${p.id}.text`) }}</span>
        <div class="bp-price">{{ runningAmount(p) }}<small> {{ runningUnit(p) }}</small></div>
        <AppButton block size="lg" :variant="p.highlighted ? 'primary' : 'secondary'" style="min-height: 44px" @click="startRunning(p)">{{ t(`marketing.pricing.running.${p.id}.cta`) }}</AppButton>
        <ul class="bp-ft"><li v-for="f in runningFeatures(p)" :key="f"><AppIcon name="check" :size="14" />{{ f }}</li></ul>
      </article>
    </div>

    <CustomRequestCard />

    <section class="pr-notes" :aria-label="t('marketing.pricing.notes.title')">
      <b>{{ t('marketing.pricing.notes.title') }}</b>
      <ul><li>{{ t('marketing.pricing.notes.n1') }}</li><li>{{ t('marketing.pricing.notes.n2') }}</li><li>{{ t('marketing.pricing.notes.n3') }}</li></ul>
    </section>
  </template>
  <FaqSection />
</template>

<style scoped>
.pr-head { padding: 20px var(--page-x) 4px; display: grid; gap: 6px; justify-items: center; text-align: center; }
.pr-head h2 { font: 500 30px/1.15 var(--font-display); margin: 0; letter-spacing: -0.01em; }
.pr-head p { margin: 0; max-width: 56ch; font-size: var(--text-sm); }
.pr-head .bp-tog { margin-top: 8px; }
.pr-notes { margin: 4px var(--page-x) 28px; padding: 16px 20px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); display: grid; gap: 8px; }
.pr-notes ul { margin: 0; padding-inline-start: 18px; display: grid; gap: 4px; font-size: var(--text-sm); color: var(--color-text-muted); }
@container app (max-width: 759px) {
  .pr-head h2 { font-size: 24px; }
}
</style>
