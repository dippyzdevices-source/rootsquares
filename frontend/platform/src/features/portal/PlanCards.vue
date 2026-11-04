<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import TaxLine from '@/components/ui/TaxLine.vue'
import { MOCK_MODULES, allowedModules } from '@/services/modulesCatalogue'
import type { LaunchPackageId, PlanPrice, PlatformSquare } from '@/services/platform'
import { EVENT_PASS_DAYS, usd } from '@rootsquares/ui/mock/pricing'
import { useFormat } from '@rootsquares/ui/composables/useFormat'

// The Billing page's big plan cards (W10-R43): everything a person needs to decide, on the card. Launch packages show the always-on parts and every module with a tick
// (included) or a dash (not included); running plans show what each does and the price, monthly or yearly. The card of the current plan says so; a bigger package offers
// the upgrade at the price of the difference; Live, Keep and the Event pass offer what can be done. Presentational: the page does the work (SquarePlanCard.vue).
const props = defineProps<{ square: PlatformSquare; prices: PlanPrice[]; busy: boolean }>()
const emit = defineEmits<{ upgrade: [pkg: LaunchPackageId]; pay: [plan: 'live' | 'keep', interval: 'month' | 'year']; change: [plan: 'keep' | 'live']; wake: [] }>()
const { t } = useI18n()
const { date } = useFormat()
const endDate = computed(() => (props.square.paid_until ? date(props.square.paid_until, { day: 'numeric', month: 'short', year: 'numeric' }) : ''))

const LADDER: LaunchPackageId[] = ['roots', 'square', 'grove']
const CORE = ['home', 'about', 'contact', 'login', 'legal', 'settings', 'media', 'admin']
const yearly = ref(props.square.billing_interval === 'year') // starts on the owner's default period (Payments page)
const price = (key: string) => props.prices.find((p) => p.key === key)?.amount_minor ?? 0
const here = computed(() => props.square.launch_package === 'custom' ? -1 : LADDER.indexOf(props.square.launch_package))
const coreNames = computed(() => CORE.map((k) => t(`plat.modules.coreItems.${k}.name`)).join(', '))

const packages = computed(() => LADDER.map((id, i) => {
  const allowed = allowedModules(MOCK_MODULES, id)
  return {
    id, current: id === props.square.launch_package, higher: here.value >= 0 && i > here.value,
    full: price(`launch.${id}`), diff: price(`launch.${id}`) - price(`launch.${props.square.launch_package}`),
    modules: MOCK_MODULES.map((m) => ({ key: m.key, label: m.label, on: allowed.includes(m.key) })),
  }
}))
const paidValid = computed(() => !!props.square.paid_until && new Date(props.square.paid_until) > new Date())
const waking = computed(() => props.square.sleep_state === 'waking')
const eventPackage = computed(() => props.square.launch_package === 'event')

const running = computed(() => (['keep', 'live', 'event'] as const).map((id) => ({
  id, current: props.square.running_plan === id,
  minor: id === 'event' ? price('launch.event') : price(`running.${id}.${yearly.value ? 'year' : 'month'}`),
})))
const per = (id: string) => (id === 'event' ? t('marketing.pricing.perEvent') : yearly.value ? t('marketing.pricing.perYear') : t('marketing.pricing.perMonth'))
const features = (id: string) => [1, 2, 3, 4].map((i) => t(`marketing.pricing.running.${id}.f${i}`, { days: EVENT_PASS_DAYS }))
</script>

<template>
  <div style="display: grid; gap: 22px" data-testid="plan-cards">
    <section style="display: grid; gap: 10px">
      <div style="display: flex; justify-content: space-between; align-items: end; gap: 12px; flex-wrap: wrap">
        <div><span class="rs-eyebrow">{{ t('portal.plan.runningEyebrow') }}</span><p class="bs-mute" style="margin: 4px 0 0; font-size: var(--text-sm)">{{ t('portal.plan.runningLede') }}</p></div>
        <div class="bp-tog" role="group" :aria-label="t('marketing.pricing.period')">
          <button type="button" :aria-pressed="!yearly" @click="yearly = false">{{ t('marketing.pricing.monthly') }}</button>
          <button type="button" :aria-pressed="yearly" @click="yearly = true">{{ t('marketing.pricing.yearly') }} <span style="font-size: 0.7rem; opacity: 0.85">{{ t('marketing.pricing.save') }}</span></button>
        </div>
      </div>
      <div class="bp-plans pc-plans">
        <article v-for="r in running" :key="r.id" class="bp-plan" :class="r.current && 'bp-plan--hl'" :data-running="r.id" :data-current="r.current || undefined">
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px">
            <h3 style="font-weight: 500; font-size: var(--text-lg); margin: 0">{{ t(`marketing.pricing.running.${r.id}.name`) }}</h3>
            <span v-if="r.current" class="rs-chip rs-chip--info">{{ t('portal.plan.yourPlan') }}</span>
          </div>
          <span class="bs-mute" style="font-size: var(--text-sm)">{{ t(`marketing.pricing.running.${r.id}.text`) }}</span>
          <div class="bp-price">{{ usd(r.minor) }}<small> {{ per(r.id) }}</small></div>
          <TaxLine :minor="r.minor" :percent="square.tax_percent" />
          <div v-if="r.id !== 'event'" style="display: grid; gap: 8px">
            <!-- One button per plan: the plan you have shows none; with a paid period running you switch for free, otherwise you pay (and the plan switches with the payment). -->
            <AppButton v-if="r.id === 'live' && waking" icon="refresh" block disabled style="min-height: 44px">{{ t('portal.plan.waking') }}</AppButton>
            <AppButton v-else-if="r.id === 'live' && square.sleep_state === 'failed'" icon="refresh" block :disabled="busy" style="min-height: 44px" @click="emit('wake')">{{ t('portal.plan.wakeAgain') }}</AppButton>
            <p v-else-if="!r.current && paidValid && r.id === 'keep' && square.pending_plan === 'keep'" class="bs-mute" style="margin: 0; font-size: var(--text-sm)" data-testid="keep-pending">{{ t('portal.plan.keepSoon', { date: endDate }) }}</p>
            <!-- A downgrade starts at the next renewal, an upgrade at once (W18-R34): the button says which and when. -->
            <AppButton v-else-if="!r.current && paidValid" icon="card" block :variant="r.id === 'live' ? 'primary' : 'secondary'" :disabled="busy || square.running_plan === 'event'" style="min-height: 44px" @click="emit('change', r.id)">{{ r.id === 'live' ? t('portal.plan.goLiveNow') : t('portal.plan.switchKeepFrom', { date: endDate }) }}</AppButton>
            <AppButton v-else-if="!r.current" icon="card" block :variant="r.id === 'live' ? 'primary' : 'secondary'" :disabled="busy || square.running_plan === 'event'" style="min-height: 44px" @click="emit('pay', r.id, yearly ? 'year' : 'month')">{{ t('portal.plan.payFor', { plan: t(`marketing.pricing.running.${r.id}.name`) }) }}</AppButton>
            <template v-else-if="r.current && paidValid">
              <p class="bs-mute" style="margin: 0; font-size: var(--text-xs)">{{ t('portal.plan.paidRunning') }}</p>
              <AppButton v-if="r.id === 'live' && square.pending_plan === 'keep'" icon="card" block variant="secondary" :disabled="busy" style="min-height: 44px" @click="emit('change', 'live')">{{ t('portal.plan.stayLive') }}</AppButton>
            </template>
            <AppButton v-else-if="r.current" icon="card" block variant="secondary" :disabled="busy" style="min-height: 44px" @click="emit('pay', r.id, yearly ? 'year' : 'month')">{{ t('portal.plan.payAgain') }}</AppButton>
          </div>
          <p v-else class="bs-mute" style="margin: 0; font-size: var(--text-xs)">{{ t('portal.plan.eventNote') }}</p>
          <ul class="bp-ft"><li v-for="f in features(r.id)" :key="f"><AppIcon name="check" :size="14" />{{ f }}</li></ul>
        </article>
      </div>
    </section>

    <section style="display: grid; gap: 10px">
      <div><span class="rs-eyebrow">{{ t('portal.plan.launchEyebrow') }}</span><p class="bs-mute" style="margin: 4px 0 0; font-size: var(--text-sm)">{{ eventPackage ? t('portal.plan.eventPackageNote') : t('portal.plan.launchLede') }}</p></div>
      <div v-if="!eventPackage" class="bp-plans pc-plans">
        <article v-for="p in packages" :key="p.id" class="bp-plan" :class="p.current && 'bp-plan--hl'" :data-package="p.id" :data-current="p.current || undefined">
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px">
            <h3 style="font-weight: 500; font-size: var(--text-lg); margin: 0">{{ t(`marketing.pricing.launch.${p.id}.name`) }}</h3>
            <span v-if="p.current" class="rs-chip rs-chip--info">{{ t('portal.plan.yourPackage') }}</span>
          </div>
          <span class="bs-mute" style="font-size: var(--text-sm)">{{ t(`marketing.pricing.launch.${p.id}.text`) }}</span>
          <div class="bp-price">{{ usd(p.full) }}<small> {{ t('marketing.pricing.oneOff') }}</small></div>
          <TaxLine :minor="p.full" :percent="square.tax_percent" />
          <AppButton v-if="p.higher" icon="card" block size="lg" :disabled="busy" style="min-height: 44px" @click="emit('upgrade', p.id)">{{ t('portal.plan.upgradeTo', { package: t(`marketing.pricing.launch.${p.id}.name`), amount: usd(p.diff) }) }}</AppButton>
          <AppButton v-else icon="circle-check" block size="lg" variant="secondary" disabled style="min-height: 44px">{{ p.current ? t('portal.plan.yourPackage') : t('portal.plan.included') }}</AppButton>
          <span v-if="p.higher" class="bs-mute" style="font-size: var(--text-xs)">{{ t('portal.plan.youPay', { amount: usd(p.diff) }) }}</span>
          <div class="pc-sec">
            <b>{{ t('portal.plan.alwaysOn') }}</b>
            <p class="bs-mute">{{ coreNames }}</p>
          </div>
          <div class="pc-sec">
            <b>{{ t('portal.plan.modules') }}</b>
            <ul class="bp-ft pc-mods">
              <li v-for="m in p.modules" :key="m.key" :class="!m.on && 'pc-off'">
                <AppIcon v-if="m.on" name="check" :size="14" /><span v-else class="pc-dash" aria-hidden="true">–</span>
                <span>{{ m.label }}<span v-if="!m.on" class="rs-sr"> ({{ t('portal.plan.notIncluded') }})</span></span>
              </li>
            </ul>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.pc-plans { padding: 0; }
.pc-plans .bp-plan[data-current] { background: var(--color-brass-subtle); } /* the active package and the active plan: light Brass */
.pc-sec { display: grid; gap: 6px; padding-top: 12px; border-top: 1px solid var(--color-border); font-size: var(--text-sm); }
.pc-sec b { font-weight: 500; }
.pc-sec p { margin: 0; font-size: var(--text-xs); }
.pc-mods { gap: 6px; }
.pc-off { color: var(--color-text-muted); }
.pc-dash { text-align: center; color: var(--color-text-muted); }
</style>
