<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import OcHead from '@/components/OcHead.vue'
import { adminApi as platform } from '@/adminApi'
import { ApiError } from '@rootsquares/ui/types/platformTypes'
import { errorText } from '@/errorText'
import { supportLink } from '@/supportUrl'
import type { SupportOverview } from '../adminTypes'

// Support access, the staff's overview (ADR 089, W23-R68): the squares whose owner has granted access right now, with "Open as support", and the requests made so far.
// A session is opened by the platform only on an active grant (403 otherwise); the token travels in the address fragment of the new window.
const { t } = useI18n()
const { date } = useFormat()
const data = ref<SupportOverview | null>(null)
const error = ref('')
const busy = ref('')
const when = (iso: string) => date(iso, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
const partName = (s: string) => t(`own.support.scopes.${s}`)
// the end time is the key fact (Support Access Flow): the clock time (with the day when it is not today) and how long is left, refreshed every half minute
const now = ref(Date.now())
let tick: ReturnType<typeof setInterval> | undefined
const endTime = (iso: string) => {
  const end = new Date(iso)
  return end.toDateString() === new Date(now.value).toDateString() ? end.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : when(iso)
}
const timeLeft = (iso: string) => {
  const minutes = Math.max(0, Math.ceil((new Date(iso).getTime() - now.value) / 60000))
  if (minutes < 60) return t('own.support.leftMin', { n: minutes })
  if (minutes < 2880) return t('own.support.leftHours', { n: Math.floor(minutes / 60) })
  return t('own.support.leftDays', { n: Math.floor(minutes / 1440) })
}
const empty = computed(() => !data.value?.active.length)

function problem(e: unknown): string {
  if (e instanceof ApiError) {
    const key = `own.support.errors.${e.code}`
    const s = t(key)
    if (s !== key) return s
  }
  return errorText(t, e)
}
async function load() {
  error.value = ''
  try { data.value = await platform.supportOverview() } catch (e) { error.value = problem(e) }
}
onMounted(() => { void load(); tick = setInterval(() => { now.value = Date.now() }, 30000) })
onBeforeUnmount(() => clearInterval(tick))

async function openAs(id: string, domain: string) {
  busy.value = id
  error.value = ''
  const win = window.open('', '_blank') // opened in the click so a pop-up blocker lets it through
  try {
    const r = await platform.supportStart(id)
    if (!win) { error.value = t('own.support.popup'); return }
    win.opener = null
    win.location.href = supportLink({ domain: r.domain || domain }, r.token)
    await load()
  } catch (e) {
    win?.close()
    error.value = problem(e)
    await load()
  } finally { busy.value = '' }
}
</script>

<template>
  <OcHead :title="t('own.support.title')" :sub="t('own.support.lede')" />
  <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>

  <section class="sv-card" data-testid="support-active">
    <h2><i class="sv-dot" aria-hidden="true" />{{ t('own.support.activeTitleN', { n: data?.active.length ?? 0 }) }}</h2>
    <p v-if="data && empty" class="sv-mute">{{ t('own.support.activeEmpty') }}</p>
    <div v-else-if="data" class="sv-hdr" aria-hidden="true">
      <span>{{ t('own.support.colSquare') }}</span><span>{{ t('own.support.colParts') }}</span><span>{{ t('own.support.colMode') }}</span><span>{{ t('own.support.colEnds') }}</span><span />
    </div>
    <div v-for="r in data?.active ?? []" :key="r.square_id" class="sv-row">
      <div>
        <b>{{ r.square_name }}</b>
        <small>{{ r.domain }}</small>
      </div>
      <div class="sv-cell"><span class="sv-lab">{{ t('own.support.colParts') }}</span><span class="sv-chips"><span v-for="s in r.scopes" :key="s" class="sv-chip">{{ partName(s) }}</span></span></div>
      <div class="sv-cell"><span class="sv-lab">{{ t('own.support.colMode') }}</span><span class="sv-pill" :class="r.allow_changes ? 'sv-pill--edit' : 'sv-pill--read'">{{ r.allow_changes ? t('own.support.pillChanges') : t('own.support.pillRead') }}</span></div>
      <div class="sv-cell sv-left"><span class="sv-lab">{{ t('own.support.colEnds') }}</span><span v-if="r.expires_at">{{ endTime(r.expires_at) }}<small>{{ timeLeft(r.expires_at) }}</small></span></div>
      <AppButton icon="external" class="sv-btn" :disabled="busy === r.square_id" @click="openAs(r.square_id, r.domain)">{{ t('own.support.openAs') }}</AppButton>
    </div>
  </section>

  <section class="sv-card" data-testid="support-requests">
    <h2>{{ t('own.support.requestsTitle') }}</h2>
    <p v-if="data && !data.requests.length" class="sv-mute">{{ t('own.support.requestsEmpty') }}</p>
    <div v-for="(r, i) in data?.requests ?? []" :key="i" class="sv-req">
      <div><b>{{ r.square_name }}</b> · {{ r.staff_name }} · {{ when(r.created_at) }}<br><span class="sv-mute">{{ r.note }}</span></div>
      <span class="sv-tag" :class="r.answered_at ? 'sv-tag--ok' : 'sv-tag--warn'">{{ r.answered_at ? t('own.support.answered') : t('own.support.waiting') }}</span>
    </div>
  </section>
</template>

<style scoped>
.sv-card { display: grid; gap: 4px; padding: 16px 20px; margin-bottom: 14px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); }
.sv-card h2 { margin: 0 0 4px; color: var(--color-text-muted); font: 600 10px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; }
.sv-mute { margin: 0; color: var(--color-text-muted); font-size: var(--text-sm); }
.sv-row, .sv-hdr { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1.5fr) 140px 130px auto; gap: 16px; align-items: center; padding: 12px 0; border-top: 1px solid var(--color-border); font-size: var(--text-sm); }
.sv-row small { display: block; color: var(--color-text-muted); }
.sv-hdr { padding: 8px 0; font-size: var(--text-xs); font-weight: 600; color: var(--color-text-muted); }
.sv-dot { display: inline-block; width: 9px; height: 9px; margin-right: 8px; border-radius: 50%; background: var(--color-success); }
.sv-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.sv-chip { padding: 3px 11px; border: 1px solid var(--color-border-strong); border-radius: var(--shape-control); background: var(--color-surface); font-size: var(--text-sm); font-weight: 500; }
.sv-pill { display: inline-block; padding: 3px 11px; border-radius: var(--shape-control); font-size: var(--text-sm); font-weight: 600; white-space: nowrap; }
.sv-pill--edit { background: var(--color-danger-subtle); color: var(--color-danger); }
.sv-pill--read { background: var(--color-surface); border: 1px solid var(--color-border-strong); color: var(--color-text); }
.sv-left { font-weight: 600; }
.sv-left small { display: block; font-weight: 500; color: var(--color-text-muted); }
.sv-lab { display: none; }
.sv-tag { padding: 3px 12px; border-radius: var(--shape-control); font-size: var(--text-xs); font-weight: 600; white-space: nowrap; }
.sv-tag--ok { background: var(--color-success-subtle); color: var(--color-success); }
.sv-tag--warn { background: var(--color-warning-subtle); color: var(--color-warning); }
.sv-req { display: flex; justify-content: space-between; gap: 16px; align-items: start; padding: 10px 0; border-top: 1px solid var(--color-border); font-size: var(--text-sm); }
/* the design (Support Access Flow) asks for sentence case at 15 px here, instead of the small spaced capitals of the other buttons (W24-R19) */
.sv-btn.sv-btn { padding: 0 18px; border-radius: var(--shape-control); font: 500 var(--text-sm) var(--font-sans); letter-spacing: 0; text-transform: none; white-space: nowrap; }
@media (max-width: 800px) { .sv-hdr { display: none; } .sv-row { grid-template-columns: 1fr; gap: 6px; } .sv-lab { display: inline; margin-right: 8px; color: var(--color-text-muted); } }
</style>
