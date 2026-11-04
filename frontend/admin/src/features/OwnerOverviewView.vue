<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { type OwnerOverview } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'
import { attentionLink } from './attentionLink'

// Owner console overview (platform admin only), from GET /owner/overview. Redesign of "Platform Overview Redesign.html" in the rootsquares design project (W11-R70):
// title with the week and a status pill, four figures (Squares large), a status strip, sign-ups per week as bars, and what needs attention.
const { t } = useI18n()
const { date } = useFormat()
const data = ref<OwnerOverview | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  try { data.value = await platform.ownerOverview(); error.value = '' } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}
onMounted(load)
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : 'default'))
const day = (iso: string) => date(iso, { day: 'numeric', month: 'short' })
const attentionText = (kind: string) => t(`own.attention.kind.${kind}`)

const weeks = computed(() => data.value?.weeks ?? [])
const thisWeek = computed(() => weeks.value[weeks.value.length - 1]?.week_start)
const newPeople = computed(() => weeks.value.slice(-4).reduce((sum, w) => sum + w.users, 0)) // the last four weeks stand for "this month"
const perOrg = computed(() => {
  const d = data.value
  if (!d || !d.organizations_total) return 0
  const n = d.squares_total / d.organizations_total
  return Number.isInteger(n) ? n : Math.round(n * 10) / 10
})
const problems = computed(() => (data.value ? data.value.squares_failed + data.value.attention.length : 0))
const pill = computed(() => {
  const d = data.value
  if (!d) return { tone: 'ok', text: '' }
  if (d.squares_failed) return { tone: 'danger', text: t('own.overview.pillFailed', { n: d.squares_failed }) }
  if (d.squares_provisioning) return { tone: 'warn', text: t('own.overview.pillBusy', { n: d.squares_provisioning }) }
  return { tone: 'ok', text: t('own.overview.pillOk') }
})
// The bars: the scale goes up in twos so the middle line is a whole number too.
const top = computed(() => Math.max(2, Math.ceil(Math.max(0, ...weeks.value.flatMap((w) => [w.users, w.squares])) / 2) * 2))
const lines = computed(() => [top.value, top.value / 2, 0])
const bar = (n: number) => `${(n / top.value) * 100}%`
</script>

<template>
  <StateGate :state="state" :rows="3" empty-title="" empty-text="" @retry="load">
    <template v-if="data">
      <div class="ov">
        <header class="ov-hd">
          <div>
            <h1 class="ov-h1">{{ t('own.overview.title') }}</h1>
            <p class="ov-sub">
              <template v-if="thisWeek">{{ t('own.overview.weekOf', { date: day(thisWeek) }) }} · </template>{{ problems ? t('own.overview.needAttention', { n: problems }) : t('own.overview.running') }}
            </p>
          </div>
          <span class="ov-pill" :class="`ov-pill--${pill.tone}`">{{ pill.text }}</span>
        </header>

        <div class="ov-kpi">
          <div class="ov-card ov-k ov-k--hero"><small>{{ t('own.overview.squares') }}</small><em class="ov-num">{{ data.squares_total }}</em><span>{{ t('own.overview.squaresSub', { ready: data.squares_ready, prov: data.squares_provisioning, failed: data.squares_failed }) }}</span></div>
          <div class="ov-card ov-k"><small>{{ t('own.overview.users') }}</small><em class="ov-num">{{ data.users_total }}</em><span>{{ t('own.overview.peopleSub', { n: newPeople }) }}</span></div>
          <div class="ov-card ov-k"><small>{{ t('own.overview.orgs') }}</small><em class="ov-num">{{ data.organizations_total }}</em><span>{{ t('own.overview.orgsSub', { n: perOrg }) }}</span></div>
          <div class="ov-card ov-k"><small>{{ t('own.overview.failed') }}</small><em class="ov-num">{{ data.squares_failed }}</em><span>{{ data.squares_failed ? t('own.overview.failedSub', { n: data.squares_failed }) : t('own.overview.failedNone') }}</span></div>
        </div>

        <div class="ov-card ov-status">
          <i class="ov-dot ov-dot--ok"><em class="ov-n">{{ data.squares_ready }}</em> {{ t('own.overview.readyLc') }}</i>
          <i class="ov-dot ov-dot--warn"><em class="ov-n">{{ data.squares_provisioning }}</em> {{ t('own.overview.provisioningLc') }}</i>
          <i v-if="data.squares_awaiting_payment" class="ov-dot ov-dot--warn"><em class="ov-n">{{ data.squares_awaiting_payment }}</em> {{ t('own.overview.awaitingLc') }}</i>
          <i class="ov-dot ov-dot--bad"><em class="ov-n">{{ data.squares_failed }}</em> {{ t('own.overview.failedLc') }}</i>
        </div>

        <div class="ov-two">
          <section class="ov-card ov-ch" :aria-label="t('own.overview.chart')">
            <div class="ov-chh">
              <h3>{{ t('own.overview.chart') }}</h3>
              <div class="ov-leg"><i class="ov-sw ov-sw--people">{{ t('own.overview.users') }}</i><i class="ov-sw ov-sw--squares">{{ t('own.overview.squares') }}</i></div>
            </div>
            <div class="ov-plot">
              <div v-for="(v, i) in lines" :key="v" class="ov-gl" :style="{ bottom: `${(i === 0 ? 1 : i === 1 ? 0.5 : 0) * 100}%` }"><span>{{ v }}</span></div>
              <div v-for="w in weeks" :key="w.week_start" class="ov-col" :title="t('own.overview.weeksNew', { users: w.users, squares: w.squares, date: day(w.week_start) })">
                <u class="ov-bar ov-bar--people" :class="!w.users && 'is-zero'" :style="{ height: bar(w.users) }" />
                <u class="ov-bar ov-bar--squares" :class="!w.squares && 'is-zero'" :style="{ height: bar(w.squares) }" />
              </div>
            </div>
            <div class="ov-xl"><span v-for="w in weeks" :key="w.week_start" :class="w.week_start === thisWeek && 'is-now'">{{ day(w.week_start) }}</span></div>
          </section>

          <section class="ov-card ov-na">
            <h3>{{ t('own.overview.attention') }}</h3>
            <div v-if="!data.attention.length" class="ov-ok">
              <AppIcon name="check" :size="22" />
              <div><b>{{ t('own.overview.allClearTitle') }}</b><span>{{ t('own.overview.allClearText') }}</span></div>
            </div>
            <div v-for="a in data.attention" :key="`${a.kind}-${a.square_id}`" class="ov-item">
              <div>
                <b>{{ a.name }}</b>
                <small>{{ attentionText(a.kind) }}<template v-if="a.detail"> · {{ a.detail }}</template> · {{ day(a.since) }}</small>
              </div>
              <AppButton icon="arrow" variant="secondary" size="sm" :to="attentionLink(a)">{{ t('own.overview.open') }}</AppButton>
            </div>
          </section>
        </div>
      </div>
    </template>
  </StateGate>
</template>
