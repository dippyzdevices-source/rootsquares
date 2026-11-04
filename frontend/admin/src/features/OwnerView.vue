<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import OcHead from '@/components/OcHead.vue'
import GoogleMark from '@rootsquares/ui/components/GoogleMark.vue'
import OcPill from '@rootsquares/ui/components/OcPill.vue'
import OcSearch from '@/components/OcSearch.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { type SquareStatus } from '@rootsquares/ui/types/platformTypes'
import { type OwnerSquare } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'
import { getTheme } from '@rootsquares/ui/themes'

// Owner console, Squares (platform admin only): every square of every organization, from GET /owner/squares. Restyled in W11-R75 from "Console Squares.html" and
// again in W23-R20 from the design project's "Squares Redesign.html": summary tiles, a search with two segmented filters, one card per square (name, status, address,
// theme and date | organisation and owner | the Google sign-in switch and the copy-callback button).
const { t } = useI18n()
const { date } = useFormat()
const { push } = useToast()
const rows = ref<OwnerSquare[]>([])
const loading = ref(true)
const error = ref('')
const q = ref('')
const fStatus = ref('')
const fGoogle = ref('')
const STATUS_FILTERS = ['', 'ready', 'provisioning', 'failed', 'suspended']
const GOOGLE_FILTERS = ['', 'enabled', 'requested']

async function load() {
  loading.value = true
  try { rows.value = await platform.ownerSquares(); error.value = '' } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}
onMounted(load)
const list = computed(() => rows.value.filter((r) =>
  `${r.name} ${r.slug} ${r.owner_email ?? ''} ${r.organization_name} ${themeName(r.theme_id)}`.toLowerCase().includes(q.value.toLowerCase())
  && (!fStatus.value || (fStatus.value === 'suspended' ? !!r.suspended_at : r.status === fStatus.value))
  && (!fGoogle.value || r.google_login === fGoogle.value)))
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : list.value.length ? 'default' : 'empty'))
// The summary tiles: only a ready square has a Google switch, so the Google counts are over the ready ones.
const readyRows = computed(() => rows.value.filter((r) => r.status === 'ready'))
const googleOn = computed(() => readyRows.value.filter((r) => r.google_login === 'enabled').length)
const needsGoogle = computed(() => readyRows.value.length - googleOn.value)
const busyId = ref('')
async function toggleGoogle(r: OwnerSquare) {
  busyId.value = r.id
  try {
    const next = await platform.setSquareGoogle(r.id, r.google_login !== 'enabled')
    r.google_login = next.google_login
    error.value = ''
    push(t(r.google_login === 'enabled' ? 'own.squares.googleOnToast' : 'own.squares.googleOffToast'), 'success')
  } catch (e) { error.value = errorText(t, e) }
  busyId.value = ''
}
async function copy(text: string | null) {
  if (!text) return
  try { await navigator.clipboard.writeText(text); push(t('own.squares.callbackCopied'), 'success') } catch { /* clipboard unavailable */ }
}
const themeName = (id: string) => getTheme(id)?.name ?? id
const day = (iso: string) => date(iso, { day: 'numeric', month: 'short', year: 'numeric' })
const statusLabel = (s: string) => (s === '' ? t('own.squares.all') : t(`plat.owner.st.${s}`))
const googleLabel = (s: string) => (s === '' ? t('own.squares.any') : s === 'enabled' ? t('own.squares.enabled') : t('own.squares.notEnabled'))
const TONE: Record<SquareStatus, 'ok' | 'warn' | 'bad'> = { ready: 'ok', provisioning: 'warn', failed: 'bad' }
</script>

<template>
  <OcHead :title="t('plat.owner.title')" :sub="t('plat.owner.sub', { n: rows.length })" />
  <div v-if="rows.length" class="sq-sum">
    <div><small>{{ t('own.squares.tileSquares') }}</small><b>{{ rows.length }}</b></div>
    <div><small>{{ t('own.squares.tileReady') }}</small><b>{{ readyRows.length }}</b></div>
    <div><small class="sq-gl"><GoogleMark :size="12" />{{ t('own.squares.tileGoogle') }}</small><b>{{ googleOn }}<em>{{ t('own.squares.tileGoogleOf', { n: readyRows.length }) }}</em></b></div>
    <div v-if="needsGoogle" class="sq-sum__al"><small>{{ t('own.squares.tileNeeds') }}</small><b>{{ needsGoogle }}</b></div>
  </div>
  <div class="sq-bar">
    <OcSearch v-model="q" class="sq-q" :placeholder="t('plat.owner.searchPh')" :label="t('common.search')" />
    <div class="sq-seg" role="group" :aria-label="t('plat.owner.filterStatus')">
      <button v-for="s in STATUS_FILTERS" :key="s" type="button" :aria-pressed="fStatus === s" @click="fStatus = s">{{ statusLabel(s) }}</button>
    </div>
    <div class="sq-seg" role="group" :aria-label="t('plat.owner.filterGoogle')">
      <button v-for="s in GOOGLE_FILTERS" :key="s" type="button" :aria-pressed="fGoogle === s" @click="fGoogle = s">{{ googleLabel(s) }}</button>
    </div>
  </div>
  <StateGate :state="state" :rows="4" :empty-title="t('plat.owner.emptyTitle')" :empty-text="t('plat.owner.emptyText')" @retry="load">
    <div class="sq-list">
      <article v-for="r in list" :key="r.id" class="sq" data-testid="square">
        <div class="sq-id">
          <span class="sq-av" aria-hidden="true">{{ r.name.trim().charAt(0).toUpperCase() }}</span>
          <div class="sq-id__t">
            <h2>
              <RouterLink :to="`/squares/${r.id}`" class="sq-name">{{ r.name }}</RouterLink>
              <OcPill :tone="r.awaiting_payment ? 'warn' : TONE[r.status]">{{ r.awaiting_payment ? t('plat.status.awaiting') : t(`plat.owner.st.${r.status}`) }}</OcPill>
              <OcPill v-if="r.suspended_at" tone="mute">{{ t('plat.owner.st.suspended') }}</OcPill>
            </h2>
            <a class="sq-url" :href="`https://${r.domain}`" target="_blank" rel="noopener" :aria-label="t('own.squares.open', { domain: r.domain })">{{ r.domain }} ↗</a>
            <div class="sq-meta">{{ t('own.squares.theme') }} · {{ themeName(r.theme_id) }} · {{ t('own.squares.created', { when: day(r.created_at) }) }}</div>
          </div>
        </div>
        <div class="sq-org"><b>{{ r.organization_name }}</b><small>{{ r.owner_email }}</small></div>
        <div class="sq-g">
          <template v-if="r.status === 'ready'">
            <div class="sq-gt"><b><GoogleMark :size="16" />{{ t('own.squares.googleLabel') }}</b><small>{{ r.google_login === 'enabled' ? t('own.squares.googleIs') : t('own.squares.googleNot') }}</small></div>
            <button type="button" class="sq-sw" role="switch" :aria-checked="r.google_login === 'enabled'" :aria-label="t('own.squares.googleSwitch', { name: r.name })" :disabled="busyId === r.id" @click="toggleGoogle(r)" />
            <button v-if="r.auth_callback_url" type="button" class="sq-ic" :title="t('plat.owner.copyCallback')" :aria-label="t('plat.owner.copyCallback')" @click="copy(r.auth_callback_url)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h9" /></svg>
            </button>
          </template>
          <span v-else class="oc-mut">–</span>
        </div>
      </article>
    </div>
  </StateGate>
</template>

<style scoped>
/* Redesign (W23-R20, from the design project's Squares Redesign.html), in the console's own tokens. */
.sq-sum { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 14px 0 20px; }
.sq-sum > div { padding: 12px 16px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); }
.sq-sum small { display: block; color: var(--color-text-muted); font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; }
.sq-sum b { font: 400 28px/1.2 var(--font-display); }
.sq-sum em { margin-inline-start: 4px; color: var(--color-text-muted); font: 12px var(--font-sans); font-style: normal; }
.sq-sum__al { background: var(--color-warning-subtle) !important; border-color: var(--color-warning) !important; }
.sq-sum__al b { color: var(--color-warning); }
.sq-bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 16px; }
.sq-q { flex: 1; min-width: 220px; max-width: none; padding: 0 18px; border-radius: var(--shape-control); } /* the shared field has a 6px corner; here it is a pill like the filters */
.sq-seg { display: flex; flex-wrap: wrap; padding: 3px; border-radius: var(--shape-control); background: var(--color-surface-sunken); }
.sq-seg button { padding: 6px 14px; border: 0; border-radius: var(--shape-control); background: none; color: var(--color-text-muted); font: 500 var(--text-sm) var(--font-sans); cursor: pointer; }
.sq-seg button:hover { color: var(--color-text); }
.sq-seg button[aria-pressed='true'] { background: var(--color-surface); color: var(--color-text); font-weight: 600; box-shadow: var(--shadow-sm); }
.sq-list { display: grid; gap: 12px; }
.sq { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr) minmax(0, 1.1fr); gap: 20px; align-items: center; padding: 18px 20px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface); }
.sq-id { display: flex; gap: 14px; align-items: center; min-width: 0; }
.sq-id__t { min-width: 0; display: grid; gap: 2px; }
.sq-av { flex: none; display: grid; place-items: center; width: 46px; height: 46px; border-radius: var(--shape-control); background: var(--color-brass-subtle); color: var(--color-brass-text); font: 500 24px var(--font-display); }
.sq h2 { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 0; font: 500 24px / 1.1 var(--font-display); }
.sq h2 .oc-pill { padding: 3px 10px; font: 600 10px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; } /* the design's small uppercase status tag */
.sq { position: relative; transition: border-color 0.15s, box-shadow 0.15s; }
.sq:hover { border-color: var(--color-border-strong); box-shadow: var(--shadow-sm); }
.sq-name { color: var(--color-text); text-decoration: none; }
.sq:hover .sq-name, .sq-name:hover { color: var(--color-brass-text); }
/* The whole card is the link to the square's page: the name's link is stretched over the card; the address, the switch and the copy button sit above it and keep their own click. */
.sq-name::after { content: ''; position: absolute; inset: 0; border-radius: var(--shape-surface); }
.sq-name:focus-visible { outline: none; }
.sq-name:focus-visible::after { outline: 2px solid var(--color-brass); outline-offset: 2px; }
.sq-url, .sq-sw, .sq-ic { position: relative; z-index: 1; }
.sq-url { color: var(--color-text-muted); font-size: var(--text-xs); text-decoration: none; word-break: break-all; }
.sq-url:hover { color: var(--color-brass-text); }
.sq-meta { color: var(--color-text-muted); font-size: var(--text-xs); }
.sq-org { display: grid; gap: 2px; min-width: 0; }
.sq-org b { font-weight: 600; }
.sq-org small { color: var(--color-text-muted); font-size: var(--text-xs); word-break: break-all; }
.sq-g { display: flex; gap: 12px; align-items: center; justify-content: flex-end; }
.sq-gt { text-align: right; line-height: 1.3; }
.sq-gt b { display: flex; gap: 6px; align-items: center; justify-content: flex-end; font-size: var(--text-sm); font-weight: 600; }
.sq-sum .sq-gl { display: flex; gap: 6px; align-items: center; }
.sq-gt small { color: var(--color-text-muted); font-size: var(--text-xs); }
.sq-sw { position: relative; flex: none; width: 42px; height: 24px; padding: 0; border: 0; border-radius: var(--shape-control); background: var(--color-border-strong); cursor: pointer; transition: background 0.15s; }
.sq-sw::after { content: ''; position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%; background: #fff; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); transition: left 0.15s; }
.sq-sw[aria-checked='true'] { background: var(--color-success); }
.sq-sw[aria-checked='true']::after { left: 21px; }
.sq-sw:focus-visible { outline: 2px solid var(--color-brass); outline-offset: 2px; }
.sq-sw:disabled { opacity: 0.6; cursor: wait; }
.sq-ic { flex: none; display: grid; place-items: center; width: 34px; height: 34px; padding: 0; border: 1px solid var(--color-border); border-radius: 50%; background: var(--color-surface); color: var(--color-text-muted); cursor: pointer; }
.sq-ic:hover { background: var(--color-surface-sunken); color: var(--color-text); }
@media (max-width: 820px) {
  .sq { grid-template-columns: 1fr; gap: 14px; }
  .sq-g { justify-content: space-between; }
  .sq-gt { order: -1; text-align: left; }
  .sq-gt b { justify-content: flex-start; }
}
</style>
