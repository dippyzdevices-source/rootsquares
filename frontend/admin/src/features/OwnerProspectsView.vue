<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import OcHead from '@/components/OcHead.vue'
import StateGate from '@rootsquares/ui/components/StateGate.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/errorText'
import { type Prospect } from '@rootsquares/ui/types/platformTypes'
import { type OwnerSquare } from '../adminTypes'
import { adminApi as platform } from '@/adminApi'

// Owner console, Prospects (W19-R22): the people who asked to speak to us on the Pricing page ("Nothing fits you?"). Work the list: set a status, write a note, delete a row
// (the person asked, or the contact is over). The details are personal data kept only here; the audit log records the id and the status, never the person's details.
const { t } = useI18n()
const router = useRouter()
const { push } = useToast()
const { date } = useFormat()
const STATUSES = ['new', 'contacted', 'won', 'closed'] as const
const rows = ref<Prospect[]>([])
const filter = ref<'all' | (typeof STATUSES)[number]>('all')
const loading = ref(true)
const error = ref('')
const busy = ref('')
const notes = ref<Record<string, string>>({})
const removing = ref<Prospect | null>(null)
const converting = ref<Prospect | null>(null) // Convert to custom package: pick the square, then the Package tab of that square opens (W19-R23)
const squares = ref<OwnerSquare[]>([])
const pick = ref('')
async function startConvert(p: Prospect) {
  converting.value = p
  pick.value = ''
  try { squares.value = (await platform.ownerSquares()).filter((s) => s.launch_package !== 'event' && s.running_plan !== 'event') } catch (e) { converting.value = null; push(errorText(t, e), 'danger') }
}
function convert() {
  const p = converting.value
  if (!p || !pick.value) return
  void router.push({ path: `/squares/${pick.value}`, query: { tab: 'package', prospect: p.id } })
}
const state = computed(() => (loading.value ? 'loading' : error.value ? 'error' : rows.value.length ? 'default' : 'empty'))
const tone = (s: string) => (s === 'new' ? 'warn' : s === 'contacted' ? 'info' : s === 'won' ? 'ok' : 'mute')
const FILTERS = ['all', ...STATUSES] as const
// All prospects are loaded once and filtered here, so every tab shows its count and a changed status moves the card at once (the list is short).
const counts = computed(() => Object.fromEntries(FILTERS.map((s) => [s, s === 'all' ? rows.value.length : rows.value.filter((r) => r.status === s).length])))
const shown = computed(() => (filter.value === 'all' ? rows.value : rows.value.filter((r) => r.status === filter.value)))
const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase()

async function load() {
  loading.value = true
  try {
    rows.value = await platform.listProspects()
    notes.value = Object.fromEntries(rows.value.map((r) => [r.id, r.notes ?? '']))
    error.value = ''
  } catch (e) { error.value = errorText(t, e) }
  loading.value = false
}
async function patch(p: Prospect, input: { status?: string; notes?: string }) {
  busy.value = p.id
  try {
    const next = await platform.updateProspect(p.id, input)
    Object.assign(p, next)
    if (input.notes !== undefined) push(t('own.prospects.noteSaved'), 'success')
  } catch (e) { push(errorText(t, e), 'danger') } finally { busy.value = '' }
}
async function remove() {
  const p = removing.value
  if (!p) return
  busy.value = p.id
  try { await platform.deleteProspect(p.id); rows.value = rows.value.filter((r) => r.id !== p.id); removing.value = null } catch (e) { push(errorText(t, e), 'danger') } finally { busy.value = '' }
}
onMounted(load)
</script>

<template>
  <OcHead :title="t('own.prospects.title')" :sub="t('own.prospects.sub')" />
  <p class="pr-priv"><i aria-hidden="true">i</i><span><b>{{ t('own.prospects.noteLead') }}</b> {{ t('own.prospects.note') }}</span></p>
  <div class="pr-tabs" role="group" :aria-label="t('own.prospects.filter')">
    <button v-for="f in FILTERS" :key="f" type="button" :aria-pressed="filter === f" @click="filter = f">{{ f === 'all' ? t('own.prospects.all') : t(`own.prospects.st.${f}`) }}<span>{{ counts[f] }}</span></button>
  </div>
  <StateGate :state="state" :rows="4" :empty-title="t('own.prospects.emptyTitle')" :empty-text="t('own.prospects.emptyText')" @retry="load">
    <p v-if="!shown.length" class="pr-none">{{ t('own.prospects.noneWithStatus') }}</p>
    <section v-for="p in shown" :key="p.id" class="oc-card pr-card" :class="{ 'pr-card--new': p.status === 'new' }" data-testid="prospect">
      <div class="pr-top">
        <span class="pr-av" aria-hidden="true">{{ initials(p.name) }}</span>
        <div class="pr-who">
          <b>{{ p.name }}</b>
          <span class="oc-mut">{{ t('own.prospects.received', { when: date(p.created_at, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) }) }}</span>
        </div>
        <select class="pr-st" :class="`pr-st--${tone(p.status)}`" :value="p.status" :disabled="busy === p.id" :aria-label="t('own.prospects.status')" @change="patch(p, { status: ($event.target as HTMLSelectElement).value })">
          <option v-for="s in STATUSES" :key="s" :value="s">{{ t(`own.prospects.st.${s}`) }}</option>
        </select>
      </div>
      <div class="pr-contact">
        <a :href="`mailto:${p.email}`"><em>{{ t('own.prospects.email') }}</em>{{ p.email }}</a>
        <a :href="`tel:${p.phone.replace(/[^+\d]/g, '')}`"><em>{{ t('own.prospects.phone') }}</em>{{ p.phone }}</a>
      </div>
      <p v-if="p.message" class="pr-msg">{{ p.message }}</p>
      <label class="pr-f"><span>{{ t('own.prospects.notes') }}</span>
        <textarea v-model="notes[p.id]" class="rs-input rs-textarea" rows="2" maxlength="4000" :placeholder="t('own.prospects.notesHint')" />
      </label>
      <div class="pr-act">
        <AppButton icon="plus" size="sm" :disabled="p.status === 'won' || p.status === 'closed'" @click="startConvert(p)">{{ t('own.prospects.convert') }}</AppButton>
        <AppButton icon="check" variant="secondary" size="sm" :loading="busy === p.id" :disabled="(notes[p.id] ?? '') === (p.notes ?? '')" @click="patch(p, { notes: notes[p.id] ?? '' })">{{ t('own.prospects.saveNote') }}</AppButton>
        <AppButton icon="trash" class="pr-del" variant="ghost" size="sm" @click="removing = p">{{ t('own.prospects.delete') }}</AppButton>
      </div>
    </section>
  </StateGate>
  <ConfirmDialog v-if="converting" tone="primary" :title="t('own.prospects.convertTitle', { name: converting.name })" :verb="t('own.prospects.convertGo')" :confirm-disabled="!pick" @cancel="converting = null" @confirm="convert">
    <p class="oc-mut" style="margin: 0 0 10px">{{ t('own.prospects.convertBody') }}</p>
    <select v-model="pick" class="rs-input" :aria-label="t('own.prospects.convertSquare')">
      <option value="" disabled>{{ t('own.prospects.convertSquare') }}</option>
      <option v-for="s in squares" :key="s.id" :value="s.id">{{ s.name }} ({{ s.slug }}) · {{ s.owner_email ?? '–' }}</option>
    </select>
  </ConfirmDialog>
  <ConfirmDialog v-if="removing" :title="t('own.prospects.deleteTitle', { name: removing.name })" :body="t('own.prospects.deleteBody')" icon="trash" :verb="t('own.prospects.delete')" @cancel="removing = null" @confirm="remove" />
</template>

<style scoped>
/* Redesign (W23-R18, from the design project's Prospects Redesign.html): a quiet privacy note, status tabs with counts, one card per prospect. Colours are the console's own tokens. */
.pr-priv { display: flex; gap: 10px; align-items: flex-start; margin: 14px 0 18px; font-size: var(--text-sm); color: var(--color-text-muted); }
.pr-priv i { flex: none; width: 16px; height: 16px; margin-top: 2px; border: 1px solid var(--color-info); border-radius: 50%; color: var(--color-info); font: 600 10px/14px var(--font-sans); font-style: normal; text-align: center; }
.pr-priv b { color: var(--color-text); font-weight: 600; }
.pr-tabs { display: flex; gap: 2px; margin-bottom: 18px; border-bottom: 1px solid var(--color-border); overflow-x: auto; overflow-y: hidden; }
.pr-tabs button { padding: 10px 16px; border: 0; border-bottom: 2px solid transparent; background: none; color: var(--color-text-muted); font: 500 var(--text-sm) var(--font-sans); cursor: pointer; white-space: nowrap; }
.pr-tabs button:hover { color: var(--color-text); }
.pr-tabs button[aria-pressed='true'] { color: var(--color-text); font-weight: 600; border-bottom-color: var(--color-brass); }
.pr-tabs span { display: inline-block; min-width: 20px; margin-inline-start: 8px; padding: 0 6px; border-radius: var(--shape-control); background: var(--color-surface-sunken); color: var(--color-text-muted); font-size: var(--text-xs); font-weight: 600; text-align: center; }
.pr-tabs button[aria-pressed='true'] span { background: var(--color-brass-subtle); color: var(--color-brass-text); }
.pr-none { margin: 0; padding: 40px; border: 1px dashed var(--color-border); border-radius: var(--shape-surface); color: var(--color-text-muted); text-align: center; }
.pr-card { margin-top: 12px; padding: 18px 20px; display: grid; gap: 14px; border-radius: var(--shape-surface); }
.pr-card--new { border-color: var(--color-warning); }
.pr-top { display: flex; align-items: center; gap: 14px; }
.pr-av { flex: none; display: grid; place-items: center; width: 40px; height: 40px; border-radius: 50%; background: var(--color-brass-subtle); color: var(--color-brass-text); font: 600 13px var(--font-sans); }
.pr-who { display: grid; gap: 2px; flex: 1; min-width: 0; }
.pr-who b { font: 500 var(--text-xl) / 1.1 var(--font-display); }
.pr-who span { font-size: var(--text-xs); }
.pr-st { flex: none; width: auto; appearance: none; -webkit-appearance: none; padding: 6px 28px 6px 14px; border: 1px solid currentColor; border-radius: var(--shape-control); background: var(--oc-bg) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M1 1l3 3 3-3' fill='none' stroke='%23555' stroke-width='1.4'/%3E%3C/svg%3E") no-repeat right 11px center; color: var(--oc-fg); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; }
.pr-st:hover:not(:disabled) { filter: brightness(0.96); }
.pr-st:focus-visible { outline: 2px solid var(--color-brass); outline-offset: 2px; }
.pr-st:disabled { opacity: 0.6; cursor: not-allowed; }
.pr-st option { color: var(--color-text); background: var(--color-surface); text-transform: none; letter-spacing: 0; }
.pr-st--ok { --oc-bg: var(--color-success-subtle); --oc-fg: var(--color-success); }
.pr-st--warn { --oc-bg: var(--color-warning-subtle); --oc-fg: var(--color-warning); }
.pr-st--info { --oc-bg: var(--color-info-subtle); --oc-fg: var(--color-info); }
.pr-st--mute { --oc-bg: var(--color-surface-sunken); --oc-fg: var(--color-text-muted); }
.pr-contact { display: flex; flex-wrap: wrap; gap: 10px; }
.pr-contact a { display: inline-flex; gap: 8px; align-items: center; padding: 5px 14px; border-radius: var(--shape-control); background: var(--color-surface-sunken); color: var(--color-text); font-size: var(--text-sm); text-decoration: none; }
.pr-contact a:hover { background: var(--color-brass-subtle); }
.pr-contact em { color: var(--color-text-muted); font: 600 10px var(--font-sans); font-style: normal; letter-spacing: 0.1em; text-transform: uppercase; }
.pr-msg { margin: 0; padding: 10px 12px; border-left: 3px solid var(--color-brass); background: var(--color-surface-sunken); font-size: var(--text-sm); white-space: pre-wrap; }
.pr-f { display: grid; gap: 5px; }
.pr-f span { color: var(--color-text-muted); font: 600 10px var(--font-sans); letter-spacing: 0.13em; text-transform: uppercase; }
.pr-f textarea { resize: vertical; min-height: 62px; padding-block: 8px; }
.pr-act { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding-top: 12px; border-top: 1px solid var(--color-border); }
.pr-del { margin-inline-start: auto; color: var(--color-text-muted); }
.pr-del:hover { background: none; color: var(--color-danger); }
@media (max-width: 620px) { .pr-top { flex-wrap: wrap; } }
</style>
