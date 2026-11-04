<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppCheck from '@rootsquares/ui/components/AppCheck.vue'
import ConfirmDialog from '@rootsquares/ui/components/ConfirmDialog.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { errorText } from '@/features/platform/errorText'
import { squareSiteUrl } from '@/services/hostMode'
import { platform, type ThemeLook } from '@/services/platform'
import { useSquare } from './squareContext'

// "Share a draft with your committee" on the Theme page (W18-R47, docs/plans/themes-starting-looks-plan.md extra 2): the look in the editor is saved as a draft and
// shown on the square's own site to anyone who opens the private link (`?look=<token>`, read by the square app). The live site is not touched until Publish. The link lives 14 days
// from each save; an optional passcode is asked for on top of the link. A draft covers colours, fonts, shapes and feel (and the kept spinners once it is published), not the theme.
const props = defineProps<{ getLook: () => ThemeLook | null; hasAny: boolean; allowed: boolean; themeId: string }>() // themeId: the theme picked on the page, shown with the draft
const emit = defineEmits<{ load: [look: Partial<ThemeLook>, themeId: string | null] }>()
const { t } = useI18n()
const { sq, set } = useSquare()
const { date } = useFormat()

const draft = computed(() => sq.value?.look_draft ?? null)
const link = computed(() => (sq.value && draft.value ? `${squareSiteUrl(sq.value)}?look=${draft.value.token}` : ''))
const expires = computed(() => (draft.value ? date(draft.value.expires_at, { day: 'numeric', month: 'short', year: 'numeric' }) : '')) // the app's date style (TS-23)
const pass = ref('')
const busy = ref(false)
const error = ref('')
const done = ref('')
const ask = ref(false)
const confirm = ref<'' | 'passcode' | 'renew' | 'remove'>('') // the question before an action that cannot be undone (TS-07)
const showPass = ref(false) // the passcode box shows what is typed on request (TS-33)
const linkEl = ref<HTMLInputElement | null>(null)
function confirmed() { const c = confirm.value; confirm.value = ''; if (c === 'passcode') void again({ passcode: '' }); else if (c === 'renew') void again({ renew: true }); else if (c === 'remove') void remove() }

async function run(job: () => Promise<unknown>, message: string) {
  busy.value = true
  error.value = ''
  done.value = ''
  try { await job(); done.value = message } catch (e) { error.value = errorText(t, e) } finally { busy.value = false; ask.value = false }
}
// Save the editor as the draft; the passcode typed is set (empty = the old one stays)
const save = () => run(async () => { const look = props.getLook(); if (!sq.value || !look) return; set(await platform.saveLookDraft(sq.value.id, look, { themeId: props.themeId, ...(pass.value.trim() ? { passcode: pass.value.trim() } : {}) })); pass.value = '' }, t('portal.theme.look.draft.saved'))
// Save the draft again as it is (a new passcode, no passcode, or a new link) without touching it with the editor
const again = (options: { passcode?: string; renew?: boolean }) => run(async () => { if (sq.value && draft.value) set(await platform.saveLookDraft(sq.value.id, draft.value.look as ThemeLook, { ...options, ...(draft.value.theme_id ? { themeId: draft.value.theme_id } : {}) })); pass.value = '' }, t('portal.theme.look.draft.saved'))
const publish = () => run(async () => { if (sq.value) set(await platform.publishLookDraft(sq.value.id)) }, t('portal.theme.look.draft.published'))
const remove = () => run(async () => { if (sq.value) set(await platform.removeLookDraft(sq.value.id)) }, t('portal.theme.look.draft.removed'))
function load() { if (draft.value) { emit('load', draft.value.look, draft.value.theme_id ?? null); done.value = t('portal.theme.look.draft.loaded') } }
async function copy() {
  error.value = ''
  try {
    // a browser may leave the clipboard call waiting (no permission, page not in focus): after 1.5 s it counts as failed
    await Promise.race([navigator.clipboard.writeText(link.value), new Promise((_, no) => window.setTimeout(() => no(new Error('timeout')), 1500))])
    done.value = t('portal.theme.look.draft.copied')
  } catch { linkEl.value?.select(); done.value = ''; error.value = t('portal.theme.look.draft.copyFailed') } // the link is selected so Ctrl+C works (TS-36)
}
</script>

<template>
  <details v-if="sq" class="td" open>
    <summary>{{ t('portal.theme.look.draft.title') }}<small v-if="draft">{{ draft.expired ? t('portal.theme.look.draft.expired') : t('portal.theme.look.draft.expires', { date: expires }) }}</small></summary>
    <div class="td-body">
      <p class="bs-mute td-note">{{ t('portal.theme.look.draft.lede') }}</p>
      <AppAlert v-if="!allowed" tone="info">{{ t('portal.theme.look.locked') }}</AppAlert>
      <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
      <AppAlert v-if="done" tone="success">{{ done }}</AppAlert>
      <AppCheck v-if="allowed" v-model="showPass" :label="t('portal.theme.look.draft.showPass')" />

      <template v-if="!draft">
        <label class="td-row"><span class="rs-label">{{ t('portal.theme.look.draft.passcode') }}</span><input v-model="pass" class="rs-input" :type="showPass ? 'text' : 'password'" autocomplete="new-password" maxlength="40" /><small class="bs-mute">{{ t('portal.theme.look.draft.passcodeHint') }}</small></label>
        <div class="td-btns">
          <AppButton icon="check" :loading="busy" :disabled="!allowed || !hasAny" @click="save">{{ t('portal.theme.look.draft.save') }}</AppButton>
          <span v-if="!hasAny" class="bs-mute td-note">{{ t('portal.theme.look.draft.empty') }}</span>
        </div>
      </template>

      <template v-else>
        <label class="td-row"><span class="rs-label">{{ t('portal.theme.look.draft.link') }}</span>
          <span class="td-link"><input ref="linkEl" class="rs-input" :value="link" readonly @focus="($event.target as HTMLInputElement).select()" /><AppButton icon="copy" variant="secondary" @click="copy">{{ t('portal.theme.look.draft.copy') }}</AppButton></span>
        </label>
        <p class="bs-mute td-note">{{ draft.has_passcode ? t('portal.theme.look.draft.passcodeSet') : t('portal.theme.look.draft.passcodeNone') }}</p>
        <label class="td-row"><span class="rs-label">{{ t('portal.theme.look.draft.passcodeChange') }}</span><input v-model="pass" class="rs-input" :type="showPass ? 'text' : 'password'" autocomplete="new-password" maxlength="40" /></label>
        <div class="td-btns">
          <AppButton icon="check" variant="secondary" :loading="busy" :disabled="!hasAny" @click="save">{{ t('portal.theme.look.draft.update') }}</AppButton>
          <AppButton icon="download" variant="ghost" :disabled="busy" @click="load">{{ t('portal.theme.look.draft.load') }}</AppButton>
          <AppButton v-if="draft.has_passcode" icon="trash" variant="ghost" :disabled="busy" @click="confirm = 'passcode'">{{ t('portal.theme.look.draft.passcodeRemove') }}</AppButton>
          <AppButton icon="refresh" variant="ghost" :disabled="busy" @click="confirm = 'renew'">{{ t('portal.theme.look.draft.renew') }}</AppButton>
          <AppButton icon="trash" variant="ghost" :disabled="busy" @click="confirm = 'remove'">{{ t('portal.theme.look.draft.remove') }}</AppButton>
        </div>
        <div class="td-btns td-pub">
          <template v-if="!ask"><AppButton icon="upload" :disabled="busy" @click="ask = true">{{ t('portal.theme.look.draft.publish') }}</AppButton></template>
          <template v-else>
            <span class="td-note">{{ t('portal.theme.look.draft.publishAsk') }}</span>
            <AppButton icon="upload" :loading="busy" @click="publish">{{ t('portal.theme.look.draft.publishYes') }}</AppButton>
            <AppButton icon="x" variant="ghost" :disabled="busy" @click="ask = false">{{ t('portal.theme.look.draft.cancel') }}</AppButton>
          </template>
        </div>
      </template>
      <p class="bs-mute td-note">{{ t('portal.theme.look.draft.note') }}</p>
    </div>
    <ConfirmDialog v-if="confirm" :title="t(`portal.theme.look.draft.confirm.${confirm}.title`)" :body="t(`portal.theme.look.draft.confirm.${confirm}.body`)" :verb="t(`portal.theme.look.draft.confirm.${confirm}.verb`)" :icon="confirm === 'renew' ? 'refresh' : 'trash'" @cancel="confirm = ''" @confirm="confirmed" />
  </details>
</template>

<style scoped>
.td { border: 1px solid var(--color-border-strong); border-radius: var(--shape-surface); background: var(--color-surface); }
.td > summary { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; padding: 12px 16px; font: 500 var(--text-lg) var(--font-sans); cursor: pointer; }
.td > summary small { color: var(--color-text-muted); font: 400 var(--text-xs) var(--font-sans); }
.td-body { display: grid; gap: 10px; padding: 0 16px 16px; }
.td-note { margin: 0; font-size: var(--text-xs); }
.td-row { display: grid; gap: 5px; max-width: 520px; }
.td-link { display: flex; gap: 8px; align-items: center; }
.td-link .rs-input { flex: 1; min-width: 0; font-family: ui-monospace, monospace; }
.td-btns { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.td-pub { padding-top: 6px; border-top: 1px solid var(--color-border); }
</style>
