<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import SegToggle from '@/components/ui/SegToggle.vue'
import { platform, ApiError, type Analytics } from '@/services/platform'
import { errorText } from '@/features/platform/errorText'
import { useSquare } from './squareContext'

// The Analytics card of the Health tab (ADR 090, W23-R79): how the square's public site is used. Counting is off until the owner switches it on. The numbers come from the
// square, are shown to the owner only and are not stored by the platform; a figure under 5 is shown as "fewer than 5"; nobody is followed from one day to the next.
const { t } = useI18n()
const { date } = useFormat()
const { sq } = useSquare()
const data = ref<Analytics | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const days = ref(30)
const askOn = ref(false)

const ranges = computed<[string, string][]>(() => [['7', t('analytics.d7')], ['30', t('analytics.d30')], ['90', t('analytics.d90')]])
const max = computed(() => Math.max(1, ...(data.value?.daily.map((d) => d.views) ?? [1])))
const empty = computed(() => !!data.value && data.value.totals.views === 0)
const shortDay = (iso: string) => date(iso, { day: 'numeric', month: 'short' })
const few = computed(() => t('analytics.few'))

function change(now: number, before: number): string {
  if (before === 0) return now === 0 ? '' : t('analytics.new')
  const pct = Math.round(((now - before) / before) * 100)
  return `${pct > 0 ? '+' : ''}${pct}%`
}
const tiles = computed(() => {
  const d = data.value
  if (!d) return []
  return [
    { key: 'visits', label: t('analytics.visits'), value: d.totals.visits, change: change(d.totals.visits, d.previous.visits) },
    { key: 'views', label: t('analytics.views'), value: d.totals.views, change: change(d.totals.views, d.previous.views) },
    { key: 'visitors', label: t('analytics.visitors'), value: d.totals.visitors, change: change(d.totals.visitors, d.previous.visitors) },
  ]
})

function problem(e: unknown): string {
  if (e instanceof ApiError) {
    const key = `analytics.errors.${e.code}`
    const s = t(key)
    if (s !== key) return s
  }
  return errorText(t, e)
}
async function load() {
  if (!sq.value) return
  loading.value = true
  error.value = ''
  try { data.value = await platform.getAnalytics(sq.value.id, days.value) } catch (e) { error.value = problem(e) } finally { loading.value = false }
}
onMounted(load)
watch(() => sq.value?.id, load)
watch(days, load)

async function setCounting(on: boolean) {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  try { await platform.setAnalytics(sq.value.id, on); askOn.value = false; await load() } catch (e) { error.value = problem(e); askOn.value = false } finally { busy.value = false }
}
</script>

<template>
  <section v-if="sq" class="an" data-testid="analytics-card">
    <div class="an__top">
      <div><h3 class="an__h">{{ t('analytics.title') }}</h3><p class="an__sub">{{ t('analytics.lede') }}</p></div>
      <AppButton v-if="data && !data.enabled" icon="chart" class="an__btn" :disabled="busy" @click="askOn = true">{{ t('analytics.switchOn') }}</AppButton>
      <AppButton v-else-if="data" icon="chart" class="an__btn an__btn--o" variant="secondary" :disabled="busy" @click="setCounting(false)">{{ t('analytics.switchOff') }}</AppButton>
    </div>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>

    <p v-if="loading && !data" class="an__mute">{{ t('analytics.loading') }}</p>
    <template v-else-if="data">
      <p v-if="!data.enabled" class="an__mute">{{ t('analytics.offText') }}</p>
      <AppAlert v-else-if="!data.reachable" tone="warning">{{ t('analytics.unreachable') }}</AppAlert>
      <AppAlert v-else-if="data.resting" tone="info">{{ t('analytics.resting') }}</AppAlert>
      <AppAlert v-else-if="!data.counting" tone="warning">{{ t('analytics.notCounting') }}</AppAlert>
      <template v-else>
        <div class="an__range"><SegToggle :model-value="String(days)" :items="ranges" :aria-label="t('analytics.range')" @update:model-value="days = Number($event)" /></div>
        <p v-if="empty" class="an__mute">{{ t('analytics.empty') }}</p>
        <template v-else>
          <div class="an__tiles">
            <div v-for="x in tiles" :key="x.key" class="an__tile">
              <span class="an__lab">{{ x.label }}</span>
              <b class="an__num">{{ x.value.toLocaleString() }}</b>
              <small v-if="x.change" class="an__chg">{{ x.change }} {{ t('analytics.vsBefore') }}</small>
            </div>
          </div>
          <div class="an__chart" role="img" :aria-label="t('analytics.chartLabel')">
            <div v-for="d in data.daily" :key="d.day" class="an__bar" :title="`${shortDay(d.day)}: ${d.views} ${t('analytics.views').toLowerCase()}, ${d.visits} ${t('analytics.visits').toLowerCase()}`">
              <i :style="{ height: `${Math.max(2, Math.round((d.views / max) * 100))}%` }" />
            </div>
          </div>
          <div v-if="data.daily.length" class="an__axis"><span>{{ shortDay(data.daily[0]!.day) }}</span><span>{{ shortDay(data.daily[data.daily.length - 1]!.day) }}</span></div>
          <p class="an__note">{{ t('analytics.visitorsNote') }}</p>

          <div class="an__tables">
            <div>
              <h4>{{ t('analytics.topPages') }}</h4>
              <p v-if="!data.pages.length" class="an__mute">{{ t('analytics.none') }}</p>
              <p v-for="p in data.pages" :key="p.path" class="an__row"><span class="an__path">{{ p.path }}</span><b>{{ p.few ? few : p.views }}</b></p>
            </div>
            <div>
              <h4>{{ t('analytics.topSources') }}</h4>
              <p v-if="!data.sources.length" class="an__mute">{{ t('analytics.none') }}</p>
              <p v-for="s in data.sources" :key="s.source" class="an__row"><span class="an__path">{{ s.source === 'direct' ? t('analytics.direct') : s.source }}</span><b>{{ s.few ? few : s.visits }}</b></p>
            </div>
          </div>
          <div v-if="data.events.length">
            <h4>{{ t('analytics.eventsTitle') }}</h4>
            <p class="an__row an__row--hd"><span>{{ t('analytics.event') }}</span><span>{{ t('analytics.eventViews') }}</span><span>{{ t('analytics.eventTickets') }}</span></p>
            <p v-for="e in data.events" :key="e.slug" class="an__row an__row--ev"><span class="an__path">{{ e.title }}</span><b>{{ e.views_few ? few : e.views }}</b><b>{{ e.tickets_few ? few : e.tickets }}</b></p>
          </div>
        </template>
      </template>
    </template>

    <ConfirmDialog v-if="askOn" tone="primary" roomy :title="t('analytics.confirmTitle')" :verb="t('analytics.confirmVerb')" :confirm-disabled="busy" @cancel="askOn = false" @confirm="setCounting(true)">
      <p><b>{{ t('analytics.counted') }}</b> {{ t('analytics.countedText') }}</p>
      <p><b>{{ t('analytics.notCountedTitle') }}</b> {{ t('analytics.notCountedText') }}</p>
      <p>{{ t('analytics.tell') }}</p>
    </ConfirmDialog>
  </section>
</template>

<style scoped>
/* Tokens only (shape.css and scheme.css): a card is a surface, a button a pill, the highlight is brass, the chosen thing is the primary colour. */
.an { display: grid; gap: 14px; margin-top: 12px; padding: 20px 24px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); }
.an__top { display: flex; justify-content: space-between; align-items: start; gap: 16px; flex-wrap: wrap; }
.an__h { margin: 0; font: 600 10px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-text-muted); }
.an__sub, .an__mute, .an__note { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--text-sm); }
.an__note { font-size: var(--text-xs); margin: 0; }
.an__btn.an__btn { padding: 0 20px; border-radius: var(--shape-control); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.an__btn--o.an__btn--o { border-color: var(--color-border); background: var(--color-surface); color: var(--color-text); }
.an__btn--o.an__btn--o:hover { border-color: var(--color-brass); background: var(--color-surface-sunken); }
.an__tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.an__tile { display: grid; gap: 2px; padding: 12px 16px; border: 1px solid var(--color-border); border-radius: var(--shape-inner); background: var(--color-surface-sunken); }
.an__lab { color: var(--color-text-muted); font-size: var(--text-xs); }
.an__num { font: 400 30px/1.1 var(--font-display); }
.an__chg { color: var(--color-text-muted); font-size: var(--text-xs); }
.an__chart { display: flex; align-items: flex-end; gap: 2px; height: 120px; padding: 8px 0 0; border-bottom: 1px solid var(--color-border); }
.an__bar { flex: 1 1 0; min-width: 2px; height: 100%; display: flex; align-items: flex-end; }
.an__bar i { display: block; width: 100%; border-radius: 2px 2px 0 0; background: var(--color-brass); opacity: 0.85; }
.an__bar:hover i { opacity: 1; background: var(--color-primary); }
.an__axis { display: flex; justify-content: space-between; color: var(--color-text-muted); font-size: var(--text-xs); }
.an__tables { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.an h4 { margin: 0 0 4px; font: 600 var(--text-sm) var(--font-sans); }
.an__row { display: flex; justify-content: space-between; gap: 12px; margin: 0; padding: 7px 0; border-top: 1px solid var(--color-border); font-size: var(--text-sm); }
.an__row--ev { display: grid; grid-template-columns: minmax(0, 1fr) 110px 110px; }
.an__row--hd { display: grid; grid-template-columns: minmax(0, 1fr) 110px 110px; color: var(--color-text-muted); font-size: var(--text-xs); border-top: 0; }
.an__path { overflow-wrap: anywhere; }
@media (max-width: 700px) { .an__tiles, .an__tables { grid-template-columns: 1fr; } }
</style>
