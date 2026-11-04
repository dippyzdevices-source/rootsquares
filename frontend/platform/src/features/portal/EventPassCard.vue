<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import type { LaunchPackageId, PlanPrice, PlatformSquare } from '@/services/platform'
import { usd } from '@rootsquares/ui/mock/pricing'
import { useFormat } from '@rootsquares/ui/composables/useFormat'

// The life of an Event pass (W11, ADR 044) on the Billing page: 45 days live, 45 days archive, then deleted. Says where the pass is and how many days are left,
// asks the owner to save the reports (and to say so), and offers the upgrade to a launch package plus Live with the price of the pass credited. Presentational: the
// page does the work (SquarePlanCard.vue).
const props = defineProps<{ square: PlatformSquare; prices: PlanPrice[]; busy: boolean }>()
const emit = defineEmits<{ upgrade: [pkg: LaunchPackageId, interval: 'month' | 'year']; confirmExport: [] }>()
const { t } = useI18n()
const { date } = useFormat()

const info = computed(() => props.square.event_pass!)
const fmt = (iso: string | null | undefined) => (iso ? date(iso, { day: 'numeric', month: 'short', year: 'numeric' }) : '')
const price = (key: string) => props.prices.find((p) => p.key === key)?.amount_minor ?? 0

const interval = ref<'month' | 'year'>(props.square.billing_interval === 'year' ? 'year' : 'month')
const targets = (['roots', 'square', 'grove'] as const).map((id) => ({ id }))
const pay = (id: LaunchPackageId) => Math.max(0, price(`launch.${id}`) - price('launch.event')) + price(`running.live.${interval.value}`)
const removed = computed(() => info.value.phase === 'removed')
</script>

<template>
  <section v-if="square.event_pass" class="ep" data-testid="event-pass-card">
    <h3 class="bs-h2" style="font-size: 20px; margin: 0">{{ t('portal.eventPass.title') }}</h3>

    <ol class="ep-steps" :aria-label="t('portal.eventPass.stepsLabel')">
      <li :class="{ 'ep-on': info.phase === 'live' }"><b>{{ t('portal.eventPass.stepLive') }}</b><span>{{ fmt(info.live_until) }}</span></li>
      <li :class="{ 'ep-on': info.phase === 'archive' }"><b>{{ t('portal.eventPass.stepArchive') }}</b><span>{{ fmt(info.archive_until) }}</span></li>
      <li :class="{ 'ep-on': removed }"><b>{{ t('portal.eventPass.stepDeleted') }}</b><span>{{ fmt(info.purge_at ?? info.archive_until) }}</span></li>
    </ol>

    <AppAlert :tone="info.phase === 'live' ? 'info' : 'warning'" :title="t(`portal.eventPass.${info.phase}Title`, { days: info.days_left })">
      {{ t(`portal.eventPass.${info.phase}Body`, { date: fmt(info.phase === 'live' ? info.live_until : info.phase === 'archive' ? info.archive_until : info.purge_at), days: info.days_left }) }}
    </AppAlert>

    <div v-if="!removed" class="ep-box">
      <h4 class="ep-h">{{ t('portal.eventPass.exportTitle') }}</h4>
      <p class="bs-mute ep-p">{{ t('portal.eventPass.exportBody') }}</p>
      <p v-if="info.export_confirmed_at" class="ep-p" data-testid="export-confirmed">{{ t('portal.eventPass.exportDone', { date: fmt(info.export_confirmed_at) }) }}</p>
      <AppButton v-else icon="download" variant="secondary" :disabled="busy" style="min-height: 44px; justify-self: start" @click="emit('confirmExport')">{{ t('portal.eventPass.exportButton') }}</AppButton>
      <p class="bs-mute ep-p" style="font-size: var(--text-xs)">{{ t('portal.eventPass.exportNote') }}</p>
    </div>

    <div v-if="!removed" class="ep-box">
      <h4 class="ep-h">{{ t('portal.eventPass.upgradeTitle') }}</h4>
      <p class="bs-mute ep-p">{{ t('portal.eventPass.upgradeBody', { credit: usd(price('launch.event')) }) }}</p>
      <div class="bp-tog" role="group" :aria-label="t('marketing.pricing.period')">
        <button type="button" :aria-pressed="interval === 'month'" @click="interval = 'month'">{{ t('marketing.pricing.monthly') }}</button>
        <button type="button" :aria-pressed="interval === 'year'" @click="interval = 'year'">{{ t('marketing.pricing.yearly') }}</button>
      </div>
      <div class="ep-up">
        <AppButton icon="card" v-for="x in targets" :key="x.id" variant="secondary" :disabled="busy" style="min-height: 44px" @click="emit('upgrade', x.id, interval)">
          {{ t('portal.eventPass.upgradeTo', { package: t(`marketing.pricing.launch.${x.id}.name`), amount: usd(pay(x.id)) }) }}
        </AppButton>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ep { display: grid; gap: 14px; }
.ep-steps { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.ep-steps li { display: grid; gap: 2px; padding: 10px 12px; border: 1px solid var(--color-border); border-radius: var(--shape-inner); background: var(--color-surface); color: var(--color-text-muted); font-size: var(--text-sm); }
.ep-steps li span { font-size: var(--text-xs); }
.ep-steps li.ep-on { border-color: var(--color-brass); background: var(--color-brass-subtle); color: var(--color-text); box-shadow: inset 0 2px 0 var(--color-brass); }
.ep-box { display: grid; gap: 10px; padding: 16px 18px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); }
.ep-h { margin: 0; font: 500 var(--text-base) var(--font-sans); }
.ep-p { margin: 0; font-size: var(--text-sm); }
.ep-up { display: flex; flex-wrap: wrap; gap: 8px; }
@media (max-width: 520px) { .ep-steps { grid-template-columns: 1fr; } }
</style>
