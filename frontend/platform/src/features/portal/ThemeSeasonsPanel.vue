<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppCheck from '@rootsquares/ui/components/AppCheck.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/features/platform/errorText'
import { platform, type LookSeason, type ThemeLook } from '@/services/platform'
import { seasonActive } from '@/themes/seasons'
import { useSquare } from './squareContext'

// "Seasonal looks" on the Theme page (W18-R49, docs/plans/themes-starting-looks-plan.md extra 3): a look (and theme) that the public site wears between two dates and then
// leaves again, for example Diwali or Christmas. A season is made from what is in the editor. The square server picks the one that covers today (UTC); with several on, the
// earlier one in the list wins. A yearly season repeats every year and may cross the new year. The whole list is saved at once (PUT /squares/:id/theme/seasons).
const props = defineProps<{ getLook: () => ThemeLook | null; hasAny: boolean; allowed: boolean; themeId: string }>() // themeId: the theme picked on the page
const emit = defineEmits<{ load: [look: Partial<ThemeLook>, themeId: string | null] }>()
const { t } = useI18n()
const { sq, set } = useSquare()
const { date } = useFormat()

const seasons = computed<LookSeason[]>(() => sq.value?.look_seasons ?? [])
const today = new Date()
const form = ref<{ id: string | null; name: string; start: string; end: string; yearly: boolean; useEditor: boolean } | null>(null)
const busy = ref(false)
const askRemove = ref<LookSeason | null>(null) // the question before a season is removed (TS-07)
const error = ref('')
const done = ref('')

const fmt = (iso: string, yearly: boolean) => date(`${iso}T00:00:00Z`, yearly ? { day: 'numeric', month: 'short', timeZone: 'UTC' } : { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
const range = (s: LookSeason) => `${fmt(s.start, s.yearly)} – ${fmt(s.end, s.yearly)}${s.yearly ? ' · ' + t('portal.theme.look.seasons.everyYear') : ''}`
const formOk = computed(() => !!form.value && form.value.name.trim() !== '' && !!form.value.start && !!form.value.end && (form.value.yearly || form.value.end >= form.value.start) && (form.value.id !== null || props.hasAny))

function add() { form.value = { id: null, name: '', start: '', end: '', yearly: false, useEditor: true }; done.value = ''; error.value = '' }
function edit(s: LookSeason) { form.value = { id: s.id, name: s.name, start: s.start, end: s.end, yearly: s.yearly, useEditor: false }; done.value = ''; error.value = '' }

async function send(list: unknown[], message: string) {
  if (!sq.value) return
  busy.value = true
  error.value = ''
  done.value = ''
  try { set(await platform.saveLookSeasons(sq.value.id, list as LookSeason[])); done.value = message; form.value = null } catch (e) { error.value = errorText(t, e) } finally { busy.value = false }
}
function saveForm() {
  const f = form.value
  if (!f || !formOk.value) return
  const fresh = f.useEditor ? { look: props.getLook(), theme_id: props.themeId } : {}
  if (f.id === null) return send([...seasons.value, { name: f.name.trim(), start: f.start, end: f.end, yearly: f.yearly, ...fresh }], t('portal.theme.look.seasons.saved'))
  return send(seasons.value.map((s) => (s.id === f.id ? { ...s, name: f.name.trim(), start: f.start, end: f.end, yearly: f.yearly, ...fresh } : s)), t('portal.theme.look.seasons.saved'))
}
const remove = (id: string) => send(seasons.value.filter((s) => s.id !== id), t('portal.theme.look.seasons.removed'))
function removeConfirmed() { const s = askRemove.value; askRemove.value = null; if (s) void remove(s.id) }
// the last day before the first day (a season that is not yearly): the form says why it cannot be saved (TS-19)
const endBefore = computed(() => !!form.value && !form.value.yearly && !!form.value.start && !!form.value.end && form.value.end < form.value.start)
const first = (id: string) => send([seasons.value.find((s) => s.id === id)!, ...seasons.value.filter((s) => s.id !== id)], t('portal.theme.look.seasons.saved'))
function load(s: LookSeason) { emit('load', s.look, s.theme_id ?? null); done.value = t('portal.theme.look.seasons.loaded') }
</script>

<template>
  <details v-if="sq" class="ts" open>
    <summary>{{ t('portal.theme.look.seasons.title') }}<small>{{ t('portal.theme.look.seasons.count', { n: seasons.length }) }}</small></summary>
    <div class="ts-body">
      <p class="bs-mute ts-note">{{ t('portal.theme.look.seasons.lede') }}</p>
      <AppAlert v-if="!allowed" tone="info">{{ t('portal.theme.look.locked') }}</AppAlert>
      <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
      <AppAlert v-if="done" tone="success">{{ done }}</AppAlert>

      <ul v-if="seasons.length" class="ts-list">
        <li v-for="s in seasons" :key="s.id" class="ts-row">
          <span class="ts-name"><b>{{ s.name }}</b><span v-if="seasonActive(s, today)" class="rs-chip rs-chip--info">{{ t('portal.theme.look.seasons.on') }}</span><small class="bs-mute">{{ range(s) }}</small></span>
          <span class="ts-btns">
            <AppButton icon="download" variant="secondary" size="sm" :disabled="busy" @click="load(s)">{{ t('portal.theme.look.seasons.load') }}</AppButton>
            <AppButton icon="edit" variant="secondary" size="sm" :disabled="busy" @click="edit(s)">{{ t('portal.theme.look.seasons.edit') }}</AppButton>
            <AppButton v-if="seasons[0]?.id !== s.id" icon="move-up" variant="secondary" size="sm" :disabled="busy" @click="first(s.id)">{{ t('portal.theme.look.seasons.first') }}</AppButton>
            <AppButton icon="trash" variant="secondary" size="sm" :disabled="busy" @click="askRemove = s">{{ t('portal.theme.look.seasons.remove') }}</AppButton>
          </span>
        </li>
      </ul>
      <p v-else class="bs-mute ts-note">{{ t('portal.theme.look.seasons.none') }}</p>

      <form v-if="form" class="ts-form" @submit.prevent="saveForm">
        <label class="ts-f"><span class="rs-label">{{ t('portal.theme.look.seasons.name') }}</span><input v-model="form.name" class="rs-input" maxlength="40" :placeholder="t('portal.theme.look.seasons.namePh')" /></label>
        <label class="ts-f"><span class="rs-label">{{ t('portal.theme.look.seasons.start') }}</span><input v-model="form.start" class="rs-input" type="date" /></label>
        <label class="ts-f"><span class="rs-label">{{ t('portal.theme.look.seasons.end') }}</span><input v-model="form.end" class="rs-input" type="date" /></label>
        <AppCheck v-model="form.yearly" :label="t('portal.theme.look.seasons.yearly')" />
        <p v-if="endBefore" class="ts-bad" role="alert">{{ t('portal.theme.look.seasons.endBefore') }}</p>
        <AppCheck v-if="form.id !== null" v-model="form.useEditor" :disabled="!hasAny" :label="t('portal.theme.look.seasons.useEditor')" />
        <p v-else class="bs-mute ts-note">{{ hasAny ? t('portal.theme.look.seasons.fromEditor') : t('portal.theme.look.seasons.empty') }}</p>
        <div class="ts-btns"><AppButton icon="check" type="submit" :loading="busy" :disabled="!allowed || !formOk">{{ t('portal.theme.look.seasons.save') }}</AppButton><AppButton icon="x" variant="ghost" :disabled="busy" @click="form = null">{{ t('portal.theme.look.draft.cancel') }}</AppButton></div>
      </form>
      <div v-else class="ts-btns"><AppButton icon="plus" variant="secondary" :disabled="!allowed || busy || seasons.length >= 12" @click="add">{{ t('portal.theme.look.seasons.add') }}</AppButton></div>
      <p class="bs-mute ts-note">{{ t('portal.theme.look.seasons.note') }}</p>
    </div>
    <ConfirmDialog v-if="askRemove" :title="t('portal.theme.look.seasons.confirmTitle', { name: askRemove.name })" :body="t('portal.theme.look.seasons.confirmBody')" :verb="t('portal.theme.look.seasons.remove')" icon="trash" @cancel="askRemove = null" @confirm="removeConfirmed" />
  </details>
</template>

<style scoped>
.ts { border: 1px solid var(--color-border-strong); border-radius: var(--shape-surface); background: var(--color-surface); }
.ts > summary { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; padding: 12px 16px; font: 500 var(--text-lg) var(--font-sans); cursor: pointer; }
.ts > summary small { color: var(--color-text-muted); font: 400 var(--text-xs) var(--font-sans); }
.ts-body { display: grid; gap: 10px; padding: 0 16px 16px; }
.ts-note { margin: 0; font-size: var(--text-xs); }
.ts-list { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.ts-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px 12px; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--shape-inner); }
.ts-name { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.ts-btns { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.ts-form { display: grid; gap: 10px; max-width: 520px; padding: 12px; border: 1px solid var(--color-border); border-radius: var(--shape-inner); }
.ts-f { display: grid; gap: 5px; }
.ts-bad { margin: 0; color: var(--color-danger); font-size: var(--text-xs); }
</style>
