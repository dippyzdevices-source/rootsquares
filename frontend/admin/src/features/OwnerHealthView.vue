<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import OcHead from '@/components/OcHead.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { errorText } from '@/errorText'
import { type OwnerHealth } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'

// Owner console, Health and settings (platform admin only), from GET /owner/health. The API sends no secret values, only booleans, hosts and status words.
// Restyled in W11-R75 from "Console Health.html": an overall pill, four counters, one row per check with its status, and the settings in a card.
// The design's 30-day uptime strips are not built: the platform keeps no history of its checks.
const { t } = useI18n()
const data = ref<OwnerHealth | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  try { data.value = await platform.ownerHealth(); error.value = '' } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}
onMounted(load)
const state = computed(() => (loading.value && !data.value ? 'loading' : error.value ? 'error' : 'default'))
const TONE = { ok: 'ok', warn: 'warn', fail: 'bad', off: 'mute' } as const
const count = (s: 'ok' | 'warn' | 'fail' | 'off') => data.value?.checks.filter((c) => c.status === s).length ?? 0
const overall = computed(() => {
  if (count('fail')) return { tone: 'bad' as const, text: t('own.health.failN', { n: count('fail') }) }
  if (count('warn')) return { tone: 'warn' as const, text: t('own.health.warnN', { n: count('warn') }) }
  return { tone: 'ok' as const, text: t('own.health.allOk') }
})
</script>

<template>
  <OcHead :title="t('own.health.title')" :sub="t('own.health.sub')">
    <OcPill v-if="data" :tone="overall.tone" large>{{ overall.text }}</OcPill>
    <button type="button" class="oc-btn" :disabled="loading" @click="load"><AppIcon name="refresh" :size="14" />{{ t('own.health.recheck') }}</button>
  </OcHead>
  <StateGate :state="state" :rows="4" empty-title="" empty-text="" @retry="load">
    <template v-if="data">
      <div class="ov-kpi" style="margin-top: 18px">
        <div class="ov-card ov-k ov-k--hero"><small>{{ t('own.health.status.ok') }}</small><em class="ov-num">{{ count('ok') }}</em><span>{{ t('own.health.ofChecks', { n: data.checks.length }) }}</span></div>
        <div class="ov-card ov-k"><small>{{ t('own.health.status.warn') }}</small><em class="ov-num">{{ count('warn') }}</em><span>{{ count('warn') ? t('own.health.needLook') : t('own.health.noneWarn') }}</span></div>
        <div class="ov-card ov-k"><small>{{ t('own.health.status.fail') }}</small><em class="ov-num">{{ count('fail') }}</em><span>{{ count('fail') ? t('own.health.needFix') : t('own.health.noneFail') }}</span></div>
        <div class="ov-card ov-k"><small>{{ t('own.health.status.off') }}</small><em class="ov-num">{{ count('off') }}</em><span>{{ t('own.health.offText') }}</span></div>
      </div>
      <div class="oc-card" style="margin-top: 12px">
        <h3 class="oc-h3">{{ t('own.health.checks') }}</h3>
        <div v-for="c in data.checks" :key="c.id" class="oc-svc">
          <div><b>{{ t(`own.health.name.${c.id}`) }}</b><small v-if="c.detail">{{ c.detail }}</small></div>
          <OcPill :tone="TONE[c.status]">{{ t(`own.health.status.${c.status}`) }}</OcPill>
        </div>
      </div>
      <div class="oc-card" style="margin-top: 12px">
        <h3 class="oc-h3">{{ t('own.health.environment') }}</h3>
        <div v-for="(v, k) in data.environment" :key="k" class="oc-env"><span>{{ t(`own.health.env.${k}`) }}</span><span>{{ v || '–' }}</span></div>
      </div>
    </template>
  </StateGate>
</template>
