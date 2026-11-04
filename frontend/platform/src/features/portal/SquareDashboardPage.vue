<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { copyText } from '@rootsquares/ui/composables/copyText'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { squareSiteUrl } from '@/services/hostMode'
import { platform } from '@/services/platform'
import { getTheme } from '@rootsquares/ui/themes'
import { presetColours } from '@/themes/lookPresets'
import { errorText } from '@/features/platform/errorText'
import { useSquare } from './squareContext'
import AttentionStrip from './AttentionStrip.vue'

// The square's detail page. W13-R35: the blocks of the owner console. Redesigned in W23-R26 from the design project's "Your Square Redesign.html" (in the user's
// brass theme): one hero (monogram, name, live line, the link with Copy, the two open buttons), a short checklist instead of two banners, the facts in a card that
// is always open, and the delete section folded away at the bottom. Events, orders and members live in the square's own admin and are not repeated here.
const { t, te } = useI18n()
const router = useRouter()
const { date } = useFormat()
const { push } = useToast()
const { sq, set } = useSquare()
const error = ref('')
const retrying = ref(false)
const confirmSlug = ref('')
const removing = ref(false)
const themeName = (id: string) => getTheme(id)?.name ?? id
const siteUrl = computed(() => (sq.value ? squareSiteUrl(sq.value) : ''))
const adminUrl = computed(() => (siteUrl.value ? `${siteUrl.value.replace(/\/?$/, '/')}admin` : '')) // the square's own admin (W23-R81), not the prototype in this app
const initial = computed(() => (sq.value?.name ?? '').trim().charAt(0).toUpperCase())
// The plan the square is on and the way up (W26-R14): the launch package by name (a square made before packages counts as Grove); on the top package the button reads Manage.
const pkg = computed(() => sq.value?.launch_package ?? 'grove')
const planName = computed(() => (pkg.value === 'custom' ? t('yourSquare.planCustom') : te(`marketing.pricing.launch.${pkg.value}.name`) ? t(`marketing.pricing.launch.${pkg.value}.name`) : pkg.value))
const canUpgrade = computed(() => pkg.value !== 'grove' && pkg.value !== 'custom')
// the colour chip of the Theme row (W26-R16): the owner's own three colours, else the theme's own (the same chip as the Theme page)
const themeChip = computed<string[]>(() => {
  const c = sq.value?.theme_overrides?.colors ?? presetColours(sq.value?.theme_id ?? '', 'light')
  return c ? [c.bg, c.ink, c.acc] : []
})
const facts = () => [
  { k: t('plat.detail.theme'), v: themeName(sq.value?.theme_id ?? ''), chip: themeChip.value },
  { k: t('plat.detail.domain'), v: sq.value?.domain ?? '', chip: [] as string[] },
  { k: t('plat.detail.database'), v: sq.value?.has_database ? t('plat.detail.dbReady') : t('plat.detail.dbPending'), chip: [] as string[] },
  { k: t('plat.detail.created'), v: sq.value ? date(sq.value.created_at, { day: 'numeric', month: 'short', year: 'numeric' }) : '', chip: [] as string[] },
]

// The line under the name and the checklist: the same states as the two banners before (archived, setting up, ready, failed; Google on or on its way).
type Tone = 'ok' | 'wait' | 'bad' | 'mute'
const live = computed<{ tone: Tone; text: string }>(() => {
  const s = sq.value
  if (!s) return { tone: 'mute', text: '' }
  if (s.archived_at) return { tone: 'mute', text: t('plat.detail.archivedTitle') }
  if (s.status === 'ready') return { tone: 'ok', text: t('yourSquare.live') }
  if (s.status === 'failed') return { tone: 'bad', text: t('plat.status.failed') }
  return { tone: 'wait', text: t(s.awaiting_payment ? 'plat.status.awaiting' : 'plat.status.provisioning') }
})
interface Step { key: string; state: 'done' | 'wait' | 'fail'; title: string; text: string; tag?: string }
const steps = computed<Step[]>(() => {
  const s = sq.value
  if (!s || s.archived_at) return []
  const list: Step[] = []
  if (s.status === 'ready') list.push({ key: 'created', state: 'done', title: t('yourSquare.stepCreated'), text: t('yourSquare.stepCreatedText') })
  else if (s.status === 'failed') list.push({ key: 'created', state: 'fail', title: t('plat.detail.failedTitle'), text: t('plat.detail.failedText', { error: s.error ?? '' }) })
  else list.push({ key: 'created', state: 'wait', title: t('plat.detail.provisioningTitle'), text: s.awaiting_payment ? t('plat.status.awaiting') : t('plat.detail.provisioningText'), tag: t('yourSquare.inProgress') })
  if (s.status === 'ready') {
    list.push(s.google_login === 'enabled'
      ? { key: 'google', state: 'done', title: t('yourSquare.stepGoogle'), text: t('plat.detail.googleOn') }
      : { key: 'google', state: 'wait', title: t('yourSquare.stepGoogle'), text: t('plat.detail.googleText'), tag: t('yourSquare.inProgress') })
  }
  return list
})
const DOT = { done: '✓', wait: '…', fail: '!' } as const

async function copyLink() {
  if (await copyText(siteUrl.value)) push(t('yourSquare.linkCopied'), 'success')
  else push(t('yourSquare.copyFailed'), 'danger')
}
async function retry() {
  if (!sq.value) return
  retrying.value = true
  try { set(await platform.retrySquare(sq.value.id)); error.value = '' } catch (e) { error.value = errorText(t, e) } finally { retrying.value = false }
}
async function remove() {
  if (!sq.value) return
  removing.value = true
  try {
    await platform.deleteSquare(sq.value.id, confirmSlug.value)
    await router.push('/dashboard')
  } catch (e) {
    error.value = errorText(t, e)
  } finally {
    removing.value = false
  }
}
</script>

<template>
  <template v-if="sq">
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <AppAlert v-if="sq.archived_at" tone="warning" :title="t('plat.detail.archivedTitle')">{{ t('plat.detail.archivedText', { date: date(sq.archived_at, { day: 'numeric', month: 'short', year: 'numeric' }) }) }}</AppAlert>
    <AttentionStrip :square-id="sq.id" />
    <section class="ys-hero">
      <div class="ys-top">
        <span class="ys-av" aria-hidden="true">{{ initial }}</span>
        <div class="ys-who">
          <h1>{{ sq.name }}</h1>
          <span class="ys-live" :class="`ys-live--${live.tone}`"><i aria-hidden="true" />{{ live.text }}</span>
        </div>
      </div>
      <template v-if="sq.status === 'ready' && !sq.archived_at">
        <div class="ys-url">
          <a :href="siteUrl" target="_blank" rel="noopener">{{ sq.domain }}</a>
          <AppButton icon="copy" class="ys-pill ys-pill--s" variant="secondary" size="sm" @click="copyLink">{{ t('yourSquare.copyLink') }}</AppButton>
        </div>
        <div class="ys-acts">
          <AppButton icon="external" class="ys-pill" :href="siteUrl" external>{{ t('plat.detail.openSite') }}</AppButton>
          <AppButton icon="external" class="ys-pill ys-pill--o" variant="secondary" :href="adminUrl" external>{{ t('plat.detail.openAdmin') }}</AppButton>
        </div>
        <p class="ys-hint">{{ t('portal.dashboard.note') }}</p>
      </template>
    </section>
    <section v-if="steps.length" class="ys-steps">
      <div v-for="s in steps" :key="s.key" class="ys-st" :class="`ys-st--${s.state}`">
        <span class="ys-dot" aria-hidden="true">{{ DOT[s.state] }}</span>
        <div><b>{{ s.title }}</b><small>{{ s.text }}</small></div>
        <span v-if="s.tag" class="ys-tag">{{ s.tag }}</span>
      </div>
    </section>
    <div v-if="sq.status === 'failed'"><AppButton icon="refresh" class="ys-pill" :loading="retrying" @click="retry">{{ t('plat.detail.retry') }}</AppButton></div>
    <section class="ys-card">
      <h2>{{ t('yourSquare.details') }}</h2>
      <dl>
        <div class="ys-r" data-testid="dashboard-plan">
          <dt>{{ t('yourSquare.plan') }}</dt>
          <dd class="ys-plan">
            <span>{{ planName }}</span>
            <AppButton icon="card" class="ys-pill ys-pill--o" size="sm" variant="secondary" :to="`/squares/${sq.id}/billing`">{{ t(canUpgrade ? 'yourSquare.upgradePlan' : 'yourSquare.managePlan') }}</AppButton>
          </dd>
        </div>
        <div v-for="f in facts()" :key="f.k" class="ys-r"><dt>{{ f.k }}</dt><dd :class="{ 'ys-plan': f.chip.length }"><i v-if="f.chip.length" class="ys-sw" aria-hidden="true"><b v-for="c in f.chip" :key="c" :style="{ background: c }" /></i>{{ f.v }}</dd></div>
      </dl>
    </section>
    <details v-if="sq.status !== 'provisioning' || sq.awaiting_payment" class="ys-card ys-dz">
      <summary>{{ t('plat.detail.deleteTitle') }}</summary>
      <div class="ys-dz__in">
        <p>{{ t('plat.detail.deleteText') }}</p>
        <form class="rs-stack" style="gap: 12px" novalidate @submit.prevent="remove">
          <AppField v-model="confirmSlug" :label="t('plat.detail.deleteConfirm', { slug: sq.slug })" autocomplete="off" />
          <div><AppButton icon="trash" class="ys-pill" type="submit" variant="danger" :loading="removing" :disabled="confirmSlug.trim().toLowerCase() !== sq.slug">{{ t('plat.detail.deleteButton') }}</AppButton></div>
        </form>
      </div>
    </details>
  </template>
</template>

<style scoped>
/* All colours are the theme's tokens (brass): the monogram is brass, focus is brass, the rest is the neutral surfaces. Every button, tag and the link bar is a pill. */
/* The design's buttons: pills, capital letters, 11px bold with spaced letters. "Open the square site" is the theme's filled button, "Open console" an outline in brass,
   "Copy link" a quiet button with a light outline (the secondary button of the theme has a dark one). The doubled class wins over the theme's button rules. */
.ys-pill.ys-pill { padding: 0 20px; border-radius: var(--shape-control); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.ys-pill--s.ys-pill--s { padding: 0 14px; border-color: var(--color-border); background: var(--color-surface); color: var(--color-text); }
.ys-pill--s.ys-pill--s:hover { border-color: var(--color-border); background: var(--color-surface-sunken); }
.ys-pill--o.ys-pill--o { border-color: var(--color-brass); background: transparent; color: var(--color-brass-text); }
.ys-pill--o.ys-pill--o:hover { border-color: var(--color-brass); background: var(--color-brass-subtle); }
.ys-hero { padding: 26px 28px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); }
.ys-top { display: flex; gap: 16px; align-items: center; }
.ys-av { flex: none; display: grid; place-items: center; width: 56px; height: 56px; border-radius: var(--shape-control); background: var(--color-brass-subtle); color: var(--color-brass-text); font: 500 30px var(--font-display); }
.ys-who h1 { margin: 0; font: 500 38px / 1.1 var(--font-display); overflow-wrap: anywhere; }
.ys-live { display: inline-flex; gap: 7px; align-items: center; margin-top: 2px; font-size: var(--text-sm); font-weight: 500; --ys-c: var(--color-text-muted); --ys-ring: var(--color-surface-sunken); color: var(--ys-c); }
.ys-live i { width: 8px; height: 8px; border-radius: 50%; background: var(--ys-c); box-shadow: 0 0 0 4px var(--ys-ring); }
.ys-live--ok { --ys-c: var(--color-success); --ys-ring: var(--color-success-subtle); }
.ys-live--wait { --ys-c: var(--color-warning); --ys-ring: var(--color-warning-subtle); }
.ys-live--bad { --ys-c: var(--color-danger); --ys-ring: var(--color-danger-subtle); }
.ys-url { display: flex; gap: 8px; align-items: center; margin: 20px 0 16px; padding: 6px 6px 6px 18px; border-radius: var(--shape-control); background: var(--color-surface-sunken); }
.ys-url a { flex: 1; min-width: 0; overflow: hidden; color: var(--color-text); font-weight: 500; text-decoration: none; text-overflow: ellipsis; white-space: nowrap; }
.ys-url a:hover { color: var(--color-brass-text); }
.ys-acts { display: flex; flex-wrap: wrap; gap: 10px; }
.ys-hint { margin: 14px 0 0; color: var(--color-text-muted); font-size: var(--text-xs); }
.ys-steps { padding: 6px 20px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); }
.ys-st { display: flex; gap: 14px; align-items: flex-start; padding: 14px 0; border-top: 1px solid var(--color-border); }
.ys-st:first-child { border-top: 0; }
.ys-dot { flex: none; display: grid; place-items: center; width: 24px; height: 24px; margin-top: 1px; border-radius: 50%; font-size: 12px; font-weight: 700; }
.ys-st--done .ys-dot { background: var(--color-success-subtle); color: var(--color-success); }
.ys-st--wait .ys-dot { background: var(--color-warning-subtle); color: var(--color-warning); }
.ys-st--fail .ys-dot { background: var(--color-danger-subtle); color: var(--color-danger); }
.ys-st b { display: block; font-weight: 600; }
.ys-st small { color: var(--color-text-muted); font-size: var(--text-sm); }
.ys-tag { margin-inline-start: auto; padding: 3px 10px; border-radius: var(--shape-control); background: var(--color-warning-subtle); color: var(--color-warning); font: 600 10px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.ys-card { padding: 6px 20px 8px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); }
.ys-card h2 { margin: 0; padding: 14px 0 8px; color: var(--color-text-muted); font: 600 10px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; }
.ys-card dl { margin: 0; }
.ys-r { display: flex; justify-content: space-between; gap: 16px; padding: 10px 0; border-top: 1px solid var(--color-border); }
.ys-r dt { color: var(--color-text-muted); }
.ys-r dd { margin: 0; font-weight: 500; text-align: right; word-break: break-all; }
.ys-sw { display: inline-flex; flex: none; border-radius: 99px; overflow: hidden; border: 1px solid var(--color-border-strong); }
.ys-sw b { width: 12px; height: 16px; display: block; }
.ys-plan { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 12px; word-break: normal; }
.ys-dz { padding: 0; border-color: var(--color-danger-subtle); }
.ys-dz summary { display: flex; justify-content: space-between; padding: 14px 20px; color: var(--color-danger); font-weight: 600; cursor: pointer; list-style: none; }
.ys-dz summary::-webkit-details-marker { display: none; }
.ys-dz summary::after { content: '+'; color: var(--color-text-muted); font-size: 18px; line-height: 1; }
.ys-dz[open] summary::after { content: '−'; }
.ys-dz summary:focus-visible { outline: 2px solid var(--color-brass); outline-offset: -2px; border-radius: var(--shape-surface); }
.ys-dz__in { padding: 0 20px 20px; border-top: 1px solid var(--color-border); }
.ys-dz__in p { margin: 14px 0; color: var(--color-text-muted); font-size: var(--text-sm); }
@media (max-width: 560px) { .ys-hero { padding: 20px; } .ys-who h1 { font-size: 30px; } .ys-url { flex-wrap: wrap; border-radius: var(--shape-surface); } }
</style>
