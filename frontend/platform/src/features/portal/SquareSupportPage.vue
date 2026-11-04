<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppTabs from '@rootsquares/ui/components/AppTabs.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import SegToggle from '@/components/ui/SegToggle.vue'
import { platform, ApiError, type SupportActivity, type SupportAuditRow, type SupportGrantInput, type SupportMinutes, type SupportScope, type SupportState } from '@/services/platform'
import { errorText } from '@/features/platform/errorText'
import { useSquare } from './squareContext'

// Support access (ADR 089, W23-R67): the owner lets rootsquares staff look at the square for a while. The page shows whether access is on (until when, which parts,
// whether changes are allowed, who opened the square), the form to allow it (how long, which parts, changes yes or no; the member list needs a second confirmation and
// is always read only), the requests staff made, and what is never reachable. Only the owner can allow or end it. The log of every use is its own tab (W23-R71),
// ten entries a page, newest first.
const { t, locale } = useI18n()
const { date } = useFormat()
const { sq } = useSquare()
const state = ref<SupportState | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')

const SCOPES: SupportScope[] = ['content', 'settings', 'health', 'members']
const CHANGEABLE: SupportScope[] = ['content', 'settings']
const minutes = ref<SupportMinutes>(60)
const scopes = ref<SupportScope[]>(['content', 'settings'])
const allowChanges = ref(false)
const membersConfirmed = ref(false)
const note = ref('')
const askAllow = ref(false)
const askEnd = ref(false)

const full = { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' } as const
const when = (iso: string) => date(iso, full)
const partName = (s: string) => t(`supportPage.scopes.${s}.name`)
const partsText = (list: string[]) => list.map(partName).join(', ')
const hasMembers = computed(() => scopes.value.includes('members'))
const canChange = computed(() => scopes.value.some((s) => CHANGEABLE.includes(s)))
const canSubmit = computed(() => scopes.value.length > 0 && (!hasMembers.value || membersConfirmed.value))
// calendar days from today to a moment (0 today, 1 tomorrow)
const dayOffset = (end: Date) => {
  const startOfDay = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  return Math.round((startOfDay(end) - startOfDay(new Date())) / 86400000)
}
// the card "access is on" (Support Access Flow): a live clock for the time left, refreshed every half minute
const now = ref(Date.now())
let tick: ReturnType<typeof setInterval> | undefined
const left = (iso: string) => {
  const minutes = Math.max(0, Math.ceil((new Date(iso).getTime() - now.value) / 60000))
  if (minutes < 60) return t('supportPage.leftMin', { n: minutes })
  if (minutes < 2880) return t('supportPage.leftHours', { n: Math.floor(minutes / 60) })
  return t('supportPage.leftDays', { n: Math.floor(minutes / 1440) })
}
const leftPercent = (g: { expires_at: string; duration_minutes: number }) => Math.max(0, Math.min(100, ((new Date(g.expires_at).getTime() - now.value) / (g.duration_minutes * 60000)) * 100))
const untilWhen = (iso: string) => {
  const end = new Date(iso)
  const days = dayOffset(end)
  const time = end.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' })
  if (days <= 0) return time
  const day = days === 1 ? new Intl.RelativeTimeFormat(locale.value, { numeric: 'auto' }).format(1, 'day') : end.toLocaleDateString(locale.value, { day: 'numeric', month: 'short' })
  return `${day}, ${time}`
}
const grantSub = (iso: string) => {
  const days = dayOffset(new Date(iso))
  const word = days <= 1 ? new Intl.RelativeTimeFormat(locale.value, { numeric: 'auto' }).format(days, 'day') : ''
  return [word.charAt(0).toLocaleUpperCase(locale.value) + word.slice(1), date(iso, { day: 'numeric', month: 'short', year: 'numeric' }), left(iso)].filter(Boolean).join(' · ')
}
// the end time is the key fact of the confirmation (Support Access Flow): its clock time with the day, and how far away it is with the full date
const ends = computed(() => {
  if (!askAllow.value) return null
  const end = new Date(Date.now() + minutes.value * 60000)
  const days = dayOffset(end)
  const word = new Intl.RelativeTimeFormat(locale.value, { numeric: 'auto' }).format(days, 'day')
  const day = days <= 1 ? word.charAt(0).toLocaleUpperCase(locale.value) + word.slice(1) : end.toLocaleDateString(locale.value, { day: 'numeric', month: 'short' })
  const time = end.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' })
  const away = new Intl.RelativeTimeFormat(locale.value, { numeric: 'always' })
  const far = minutes.value < 1440 ? away.format(minutes.value / 60, 'hour') : away.format(minutes.value / 1440, 'day')
  return { head: `${day}, ${time}`, sub: `${far} · ${date(end.toISOString(), { day: 'numeric', month: 'short', year: 'numeric' })}` }
})
const durations = computed<[string, string][]>(() => [['60', t('supportPage.d60')], ['1440', t('supportPage.d1440')], ['10080', t('supportPage.d10080')]])
const durationName = (m: number) => t(`supportPage.d${m}`)
// the sentence under the form (Support Access Redesign): what staff will be able to do, as the owner has set it so far
const chosenParts = computed(() => new Intl.ListFormat(locale.value, { style: 'long', type: 'conjunction' }).format(SCOPES.filter((s) => scopes.value.includes(s)).map((s) => partName(s).toLocaleLowerCase(locale.value))))

watch(canChange, (ok) => { if (!ok) allowChanges.value = false })
watch(hasMembers, (on) => { if (!on) membersConfirmed.value = false })

function toggle(s: SupportScope) {
  scopes.value = scopes.value.includes(s) ? scopes.value.filter((x) => x !== s) : [...scopes.value, s]
}
function problem(e: unknown): string {
  if (e instanceof ApiError) {
    const key = `supportPage.errors.${e.code}`
    const s = t(key)
    if (s !== key) return s
  }
  return errorText(t, e)
}

// the two tabs: the access (grant or form, requests, what is never reachable) and the activity (the log, paged)
const tab = ref<'access' | 'activity'>('access')
const PER_PAGE = 15
const page = ref(1)
const activity = ref<SupportActivity | null>(null)
const pages = computed(() => Math.max(1, Math.ceil((activity.value?.total ?? 0) / PER_PAGE)))
const tabs = computed(() => [
  { id: 'access', label: t('supportPage.tabAccess') },
  { id: 'activity', label: t('supportPage.tabActivity'), count: activity.value?.total },
])

async function loadActivity() {
  if (!sq.value) return
  try { activity.value = await platform.getSupportActivity(sq.value.id, page.value, PER_PAGE) } catch (e) { error.value = problem(e) }
}
function go(p: number) {
  page.value = Math.min(pages.value, Math.max(1, p))
  void loadActivity()
}

async function load() {
  if (!sq.value) return
  loading.value = true
  error.value = ''
  try { state.value = await platform.getSupport(sq.value.id) } catch (e) { error.value = problem(e) } finally { loading.value = false }
  page.value = 1 // a change (allow, end) puts a new line at the top of the log
  await loadActivity()
}
onMounted(() => { void load(); tick = setInterval(() => { now.value = Date.now() }, 30000) })
onBeforeUnmount(() => clearInterval(tick))
watch(() => sq.value?.id, load)

async function allow() {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  const input: SupportGrantInput = { duration_minutes: minutes.value, scopes: SCOPES.filter((s) => scopes.value.includes(s)), allow_changes: allowChanges.value, members_confirmed: membersConfirmed.value, note: note.value.trim() || undefined }
  try {
    await platform.createSupportGrant(sq.value.id, input)
    askAllow.value = false
    note.value = ''
    await load()
  } catch (e) { error.value = problem(e); askAllow.value = false } finally { busy.value = false }
}
async function end() {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  try { state.value = await platform.revokeSupport(sq.value.id); askEnd.value = false; page.value = 1; await loadActivity() } catch (e) { error.value = problem(e); askEnd.value = false } finally { busy.value = false }
}

function line(a: SupportAuditRow): string {
  const mode = a.allow_changes ? t('supportPage.mode.changes') : t('supportPage.mode.read')
  const ended = a.ended_by ? t(`supportPage.ended.${a.ended_by}`) : ''
  // an owner's own line says "You"; another owner's says their name; a person who has erased their account is "Someone"
  const who = a.by_you ? t('supportPage.you') : a.who || t('supportPage.someone')
  return t(`supportPage.log.${a.action.replace('support.', '')}`, { who, parts: partsText(a.scopes), mode, how: ended }, { default: a.action })
}
</script>

<template>
  <template v-if="sq">
    <div class="bw-hd"><h2 class="bs-h2" style="font-size: 28px">{{ t('portal.nav.support') }}</h2><p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('portal.support.lede') }}</p></div>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>

    <div v-if="loading && !state" class="bx-list" aria-busy="true"><span class="bx-sk" style="height: 120px" /></div>
    <AppTabs v-else-if="state" v-model="tab" :tabs="tabs" :label="t('portal.nav.support')">
     <div v-if="tab === 'access'" class="su-stack">
      <aside class="su-lock">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="11" width="16" height="10" rx="2.5" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
        <div><b>{{ t('supportPage.neverTitle') }}</b><span>{{ t('supportPage.neverText') }}</span></div>
      </aside>
      <!-- on: the active grant -->
      <section v-if="state.grant" class="su-card su-on" data-testid="support-on">
        <div class="su-on__top">
          <div>
            <span class="su-badge">{{ t('supportPage.onTitle') }}</span>
            <h3 class="su-on__head"><i18n-t keypath="supportPage.onHead" tag="span"><template #time><em>{{ untilWhen(state.grant.expires_at) }}</em></template></i18n-t></h3>
            <p class="su-on__sub">{{ grantSub(state.grant.expires_at) }}</p>
          </div>
          <AppButton v-if="state.can_manage" icon="ban" class="su-end-btn" variant="secondary" :disabled="busy" @click="askEnd = true">{{ t('supportPage.endNow') }}</AppButton>
        </div>
        <div class="su-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="Math.round(leftPercent(state.grant))" :aria-label="left(state.grant.expires_at)"><i :style="{ width: `${leftPercent(state.grant)}%` }" /></div>
        <div class="su-chips">
          <span v-for="s in state.grant.scopes" :key="s" class="su-chip">{{ partName(s) }}</span>
          <span class="su-pill" :class="state.grant.allow_changes ? 'su-pill--edit' : 'su-pill--read'">{{ state.grant.allow_changes ? t('supportPage.pillOnChanges') : t('supportPage.pillRead') }}</span>
        </div>
        <div class="su-ob">
          <b>{{ t('supportPage.openedBy') }}</b>
          <span v-if="!state.grant.sessions.length" class="su-mute">{{ t('supportPage.nobody') }}</span>
          <div v-else class="su-ob__list">
            <span v-for="x in state.grant.sessions" :key="x.id">{{ x.staff_name }} · {{ when(x.started_at) }} · <span class="su-mute">{{ x.ended_at ? t(`supportPage.ended.${x.ended_by ?? 'staff'}`) : t('supportPage.open') }}</span></span>
          </div>
        </div>
      </section>

      <!-- off: the form (Support Access Redesign: status pill, option cards, the editing group, a sentence that says what will happen) -->
      <section v-else class="su-card su-card--form" data-testid="support-off">
        <div class="su-hd"><h3 class="su-h">{{ t('supportPage.allowTitle') }}</h3><span class="su-st">{{ t('supportPage.statusOff') }}</span></div>
        <p class="su-text">{{ t('supportPage.offText') }}</p>
        <template v-if="state.can_manage">
          <h4 class="su-label">{{ t('supportPage.howLong') }}</h4>
          <SegToggle :model-value="String(minutes)" :items="durations" :aria-label="t('supportPage.howLong')" @update:model-value="minutes = Number($event) as SupportMinutes" />
          <h4 class="su-label">{{ t('supportPage.which') }}</h4>
          <div class="su-opts">
            <label v-for="s in SCOPES" :key="s" class="su-opt" :class="scopes.includes(s) && 'su-opt--on'">
              <input type="checkbox" class="su-cb" :checked="scopes.includes(s)" @change="toggle(s)">
              <span class="su-bx" aria-hidden="true"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7" /></svg></span>
              <span><b>{{ partName(s) }}</b><small>{{ t(`supportPage.scopes.${s}.hint`) }}</small></span>
            </label>
            <label v-if="hasMembers" class="su-opt su-opt--warn" :class="membersConfirmed && 'su-opt--on'">
              <input v-model="membersConfirmed" type="checkbox" class="su-cb">
              <span class="su-bx" aria-hidden="true"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7" /></svg></span>
              <span><b>{{ t('supportPage.membersConfirm') }}</b></span>
            </label>
          </div>
          <section class="su-caution">
            <div class="su-caution__hd">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3L2 20h20L12 3z" /><path d="M12 10v4M12 17.2v.1" /></svg>
              <div><b>{{ t('supportPage.editing') }}</b><span>{{ t('supportPage.editingHint') }}</span></div>
            </div>
            <label class="su-opt" :class="[!canChange && 'su-opt--off', allowChanges && 'su-opt--on']">
              <input v-model="allowChanges" type="checkbox" class="su-cb" :disabled="!canChange">
              <span class="su-bx" aria-hidden="true"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7" /></svg></span>
              <span><b>{{ t('supportPage.allowChanges') }}</b><small>{{ canChange ? t('supportPage.allowChangesHint') : t('supportPage.allowChangesOff') }}</small></span>
            </label>
          </section>
          <h4 class="su-label">{{ t('supportPage.note') }}</h4>
          <input v-model="note" class="rs-input" maxlength="300" :placeholder="t('supportPage.notePlaceholder')">
          <div class="su-act">
            <i18n-t v-if="scopes.length" keypath="supportPage.sum" tag="p" class="su-sum">
              <template #mode><b>{{ allowChanges ? t('supportPage.sumViewEdit') : t('supportPage.sumView') }}</b></template>
              <template #parts>{{ chosenParts }}</template>
              <template #duration><b>{{ durationName(minutes) }}</b></template>
            </i18n-t>
            <p v-else class="su-sum">{{ t('supportPage.sumNone') }}</p>
            <p v-if="allowChanges" class="su-sum su-sum--warn">{{ t('supportPage.sumEditing') }}</p>
            <div class="su-go"><AppButton icon="send" class="su-btn" :disabled="!canSubmit || busy" @click="askAllow = true">{{ t('supportPage.allowBtn') }}</AppButton></div>
          </div>
        </template>
        <AppAlert v-else tone="info">{{ t('supportPage.ownerOnly') }}</AppAlert>
      </section>

      <!-- requests -->
      <section class="su-card" :class="!state.requests.length && 'su-card--row'">
        <h3 class="su-h">{{ t('supportPage.requestsTitle') }}</h3>
        <p v-if="!state.requests.length" class="su-mute">{{ t('supportPage.requestsEmpty') }}</p>
        <p v-for="r in state.requests" :key="r.id" class="su-row">
          <b>{{ r.staff_name }}</b> · {{ when(r.created_at) }}<template v-if="r.answered_at"> · <span class="su-mute">{{ t('supportPage.answered') }}</span></template><br>
          <span class="su-mute">{{ r.note }}</span>
        </p>
      </section>

     </div>

     <!-- activity: the log of every use, ten a page -->
     <section v-else class="su-card" data-testid="support-log">
      <h3 class="su-h">{{ t('supportPage.activityTitle') }}</h3>
      <p v-if="activity && !activity.items.length" class="su-mute">{{ t('supportPage.activityEmpty') }}</p>
      <p v-for="(a, i) in activity?.items ?? []" :key="`${page}-${i}`" class="su-row su-log"><span class="su-mute">{{ when(a.at) }}</span><span>{{ line(a) }}</span></p>
      <nav v-if="activity && activity.total > PER_PAGE" class="su-pager" :aria-label="t('supportPage.pager')">
        <span class="su-mute">{{ t('supportPage.range', { from: (page - 1) * PER_PAGE + 1, to: Math.min(page * PER_PAGE, activity.total), total: activity.total }) }}</span>
        <span class="su-pager__go">
          <button type="button" class="su-pg" :disabled="page <= 1" @click="go(page - 1)">{{ t('supportPage.prev') }}</button>
          <span class="su-pager__now">{{ t('supportPage.pageOf', { page, pages }) }}</span>
          <button type="button" class="su-pg" :disabled="page >= pages" @click="go(page + 1)">{{ t('supportPage.next') }}</button>
        </span>
      </nav>
     </section>
    </AppTabs>

    <ConfirmDialog v-if="askAllow" tone="primary" roomy :title="t('supportPage.confirmTitle')" :verb="t('supportPage.confirmVerb')" :confirm-disabled="busy" @cancel="askAllow = false" @confirm="allow">
      <div class="su-conf">
        <div class="su-conf__row"><span>{{ t('supportPage.confirmChanges') }}</span><span class="su-pill" :class="allowChanges ? 'su-pill--edit' : 'su-pill--read'">{{ allowChanges ? t('supportPage.pillChanges') : t('supportPage.pillRead') }}</span></div>
        <div class="su-conf__row"><span>{{ t('supportPage.confirmParts') }}</span><span class="su-chips"><span v-for="s in SCOPES.filter((x) => scopes.includes(x))" :key="s" class="su-chip">{{ partName(s) }}</span></span></div>
        <div class="su-conf__row"><span>{{ t('supportPage.confirmEnds') }}</span><span class="su-end">{{ ends?.head }}<small>{{ ends?.sub }}</small></span></div>
      </div>
      <p class="su-fine">{{ t('supportPage.confirmText') }}</p>
    </ConfirmDialog>
    <ConfirmDialog v-if="askEnd" tone="primary" roomy :title="t('supportPage.endTitle')" :verb="t('supportPage.endVerb')" :confirm-disabled="busy" @cancel="askEnd = false" @confirm="end">
      <p>{{ t('supportPage.endText') }}</p>
    </ConfirmDialog>
  </template>
</template>

<style scoped>
/* Tokens only (shape.css and scheme.css): cards are surfaces, buttons and tags are pills, the chosen thing is the primary colour, the highlight is brass. */
.su-card { display: grid; gap: 10px; padding: 20px 24px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); }
.su-stack { display: grid; gap: 16px; }
.su-pager { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; padding-top: 12px; border-top: 1px solid var(--color-border); }
.su-pager__go { display: inline-flex; align-items: center; gap: 12px; }
.su-pager__now { font-size: var(--text-sm); font-weight: 600; }
.su-pg { padding: 6px 16px; border: 1px solid var(--color-border); border-radius: var(--shape-control); background: var(--color-surface); color: var(--color-text); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; }
.su-pg:hover:not(:disabled) { border-color: var(--color-brass); background: var(--color-surface-sunken); }
.su-pg:disabled { opacity: 0.45; cursor: not-allowed; }
.su-h { margin: 0; font: 600 10px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-text-muted); }
.su-text { margin: 0; color: var(--color-text-muted); font-size: var(--text-sm); }
.su-mute { color: var(--color-text-muted); font-size: var(--text-sm); }
.su-row { margin: 0; padding: 8px 0; border-top: 1px solid var(--color-border); font-size: var(--text-sm); }
.su-log { display: grid; grid-template-columns: 170px 1fr; gap: 12px; }
.su-label { margin: 12px 0 0; font: 600 var(--text-sm) var(--font-sans); }
.su-opt { position: relative; display: flex; gap: 14px; align-items: flex-start; padding: 14px 16px; border: 1px solid var(--color-border); border-radius: var(--shape-inner); background: var(--color-surface); cursor: pointer; }
.su-opt:hover:not(.su-opt--off) { border-color: var(--color-brass); }
/* chosen = a brass border and a soft brass tint (the highlight role, one pixel like every marked card); the filled box carries the primary colour */
.su-opt--on, .su-opt--on:hover { border-color: var(--color-brass); background: var(--color-brass-subtle); }
.su-opt b { display: block; }
.su-opt small { display: block; color: var(--color-text-muted); font-size: var(--text-xs); }
.su-opt--warn { border-color: var(--color-warning); background: var(--color-warning-subtle); }
.su-opt--warn:hover:not(.su-opt--off), .su-opt--warn.su-opt--on, .su-opt--warn.su-opt--on:hover { border-color: var(--color-warning); background: var(--color-warning-subtle); }
.su-opt--off { opacity: 0.6; cursor: not-allowed; }
.su-cb { position: absolute; opacity: 0; width: 22px; height: 22px; margin: 0; }
.su-bx { flex: none; display: grid; place-items: center; width: 22px; height: 22px; margin-top: 1px; border: 1.5px solid var(--color-border-strong); border-radius: var(--shape-inner); background: var(--color-surface); color: var(--color-on-primary); }
.su-bx svg { opacity: 0; }
.su-opt--on .su-bx { background: var(--color-primary); border-color: var(--color-primary); }
.su-opt--on .su-bx svg { opacity: 1; }
.su-cb:focus-visible + .su-bx { outline: 3px solid var(--color-brass); outline-offset: 2px; }
.su-go { margin-top: 8px; }
.su-btn.su-btn { padding: 0 20px; border-radius: var(--shape-control); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.su-card--form { gap: 14px; }
.su-card--row { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.su-card--row .su-mute { margin: 0; }
/* the notice at the top: what is never reachable (Support Access Redesign) */
.su-lock { display: flex; gap: 14px; align-items: flex-start; padding: 16px 20px; background: var(--color-surface-sunken); border: 1px solid var(--color-border); border-radius: var(--shape-surface); color: var(--color-text); }
.su-lock svg { flex: none; margin-top: 2px; }
.su-lock b { display: block; font-size: var(--text-sm); }
.su-lock span { display: block; max-width: 62ch; font-size: var(--text-sm); color: var(--color-text-muted); }
.su-hd { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.su-st { display: inline-flex; align-items: center; gap: 8px; padding: 5px 14px; border-radius: var(--shape-control); background: var(--color-surface-sunken); font-size: var(--text-xs); font-weight: 600; }
.su-st::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--color-text-muted); }
.su-opts { display: grid; gap: 10px; }
/* the Editing group is a caution card (design Support Access Redesign): a warning sign, a title and one sentence, then the option. Red-tinged like the Danger zone: the design's rust is mapped to the danger tokens, a 1.5 px border (W24-R18) */
.su-caution { display: grid; gap: 14px; padding: 16px; border: 1.5px solid var(--color-danger); border-radius: var(--shape-surface); background: color-mix(in srgb, var(--color-danger-subtle) 40%, var(--color-surface)); }
.su-caution__hd { display: flex; gap: 12px; align-items: flex-start; color: var(--color-danger); }
.su-caution__hd svg { flex: none; margin-top: 2px; }
.su-caution__hd b { display: block; font-size: var(--text-sm); }
.su-caution__hd span { display: block; font-size: var(--text-sm); color: var(--color-text-muted); }
.su-caution .su-opt:hover:not(.su-opt--off) { border-color: var(--color-danger); }
.su-caution .su-opt--on, .su-caution .su-opt--on:hover { border-color: var(--color-danger); background: var(--color-danger-subtle); }
/* the card "access is on" (design Support Access Flow): a green badge, the end time as the headline, the time left as a bar (W24-R20) */
.su-on { gap: 18px; padding: 24px 28px; border: 1px solid var(--color-brass); }
.su-on__top { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.su-badge { display: inline-flex; align-items: center; gap: 8px; padding: 5px 12px; border-radius: var(--shape-control); background: var(--color-success-subtle); color: var(--color-success); font-size: var(--text-sm); font-weight: 600; }
.su-badge::before { content: ""; width: 9px; height: 9px; border-radius: 50%; background: var(--color-success); }
.su-on__head { margin: 12px 0 4px; font-family: var(--font-display); font-weight: 500; font-size: clamp(28px, 3.4vw, 38px); line-height: 1.1; }
.su-on__head em { font-style: normal; color: var(--color-brass-text); }
.su-on__sub { margin: 0; font-size: var(--text-sm); color: var(--color-text-muted); }
.su-end-btn.su-end-btn { padding: 0 20px; border: 1.5px solid var(--color-danger); border-radius: var(--shape-control); background: var(--color-surface); color: var(--color-danger); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.su-end-btn.su-end-btn:hover:not(:disabled) { background: var(--color-danger); color: var(--color-surface); }
.su-bar { height: 6px; border-radius: var(--shape-control); background: var(--color-surface-sunken); overflow: hidden; }
.su-bar i { display: block; height: 100%; background: var(--color-success); }
.su-ob { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding-top: 16px; border-top: 1px solid var(--color-border); font-size: var(--text-sm); }
.su-ob__list { display: grid; gap: 4px; justify-items: end; }
.su-act { display: grid; gap: 10px; margin-top: 6px; padding-top: 18px; border-top: 1px solid var(--color-border); }
.su-sum { margin: 0; font-size: var(--text-sm); }
.su-sum--warn { color: var(--color-warning); font-weight: 600; }
.su-conf { display: grid; padding: 4px 16px; border: 1px solid var(--color-border); border-radius: var(--shape-inner); background: var(--color-surface-sunken); }
.su-conf__row { display: grid; grid-template-columns: 96px 1fr; gap: 12px; align-items: center; padding: 12px 0; border-top: 1px solid var(--color-border); font-size: var(--text-sm); }
.su-conf__row:first-child { border-top: 0; }
.su-conf__row > span:first-child { color: var(--color-text-muted); }
.su-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.su-chip { padding: 3px 11px; border: 1px solid var(--color-border-strong); border-radius: var(--shape-control); background: var(--color-surface); font-size: var(--text-sm); font-weight: 500; }
.su-pill { justify-self: start; padding: 3px 11px; border-radius: var(--shape-control); font-size: var(--text-sm); font-weight: 600; }
.su-pill--edit { background: var(--color-danger-subtle); color: var(--color-danger); }
.su-pill--read { background: var(--color-surface); border: 1px solid var(--color-border-strong); color: var(--color-text); }
.su-end { font: 600 var(--text-lg) var(--font-sans); }
.su-end small { display: block; font-size: var(--text-sm); font-weight: 500; color: var(--color-text-muted); }
.su-fine { margin: 0; font-size: var(--text-sm); color: var(--color-text-muted); }
@media (max-width: 700px) { .su-log { grid-template-columns: 1fr; gap: 0; } }
</style>
