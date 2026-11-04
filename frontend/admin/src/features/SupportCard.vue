<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { useFormat } from '@rootsquares/ui/composables/useFormat'
import { useToast } from '@rootsquares/ui/components/useToast'
import { adminApi as platform } from '@/adminApi'
import { ApiError } from '@rootsquares/ui/types/platformTypes'
import { errorText } from '@/errorText'
import { supportLink } from '@/supportUrl'
import type { SupportSquareState } from '../adminTypes'

// Support access on a square's page (ADR 089, W23-R68): is the owner's grant on, for what and until when; ask for access with a note; open the square's own admin as support.
// Staff see the parts and the end time only, never the owner's note or any content.
const props = defineProps<{ squareId: string; slug: string }>()
const { t } = useI18n()
const { date } = useFormat()
const { push } = useToast()
const state = ref<SupportSquareState | null>(null)
const error = ref('')
const busy = ref(false)
const asking = ref(false)
const note = ref('')

const ends = computed(() => (state.value?.expires_at ? date(state.value.expires_at, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''))
const parts = computed(() => (state.value?.scopes ?? []).map((s) => t(`own.support.scopes.${s}`)).join(', '))
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
  try { state.value = await platform.supportSquare(props.squareId) } catch (e) { error.value = problem(e) }
}
onMounted(load)
watch(() => props.squareId, load)

async function send() {
  busy.value = true
  error.value = ''
  try {
    await platform.supportRequest(props.squareId, note.value.trim())
    push(t('own.support.requestSent'), 'success')
    asking.value = false
    note.value = ''
  } catch (e) { error.value = problem(e) } finally { busy.value = false }
}
async function openAs() {
  busy.value = true
  error.value = ''
  const win = window.open('', '_blank') // opened first, in the click, so a pop-up blocker lets it through; the address follows
  try {
    const r = await platform.supportStart(props.squareId)
    if (!win) { error.value = t('own.support.popup'); return }
    win.opener = null
    win.location.href = supportLink({ domain: r.domain, slug: props.slug }, r.token)
  } catch (e) {
    win?.close()
    error.value = problem(e)
    await load()
  } finally { busy.value = false }
}
</script>

<template>
  <section v-if="state" id="support" class="spc" data-testid="support-card">
    <h2>{{ t('own.support.card') }}</h2>
    <AppAlert v-if="error" tone="danger">{{ error }}</AppAlert>
    <template v-if="state.active">
      <p class="spc__big">{{ t('own.support.cardOn', { date: ends }) }}</p>
      <div class="spc__tags"><span class="spc__tag">{{ parts }}</span><span class="spc__tag" :class="state.allow_changes ? 'spc__tag--warn' : 'spc__tag--ok'">{{ state.allow_changes ? t('own.support.changes') : t('own.support.read') }}</span></div>
      <AppButton icon="external" class="spc__btn" :disabled="busy" @click="openAs">{{ t('own.support.openAs') }}</AppButton>
    </template>
    <template v-else>
      <p class="spc__text">{{ t('own.support.cardOff') }}</p>
      <div v-if="asking" class="spc__form">
        <label class="rs-label" for="spc-note">{{ t('own.support.requestNote') }}</label>
        <input id="spc-note" v-model="note" class="rs-input" maxlength="300">
        <div class="spc__row"><AppButton icon="send" class="spc__btn" :disabled="busy || note.trim().length < 3" @click="send">{{ t('own.support.requestSend') }}</AppButton><AppButton icon="x" class="spc__btn spc__btn--o" variant="secondary" @click="asking = false">{{ t('common.cancel') }}</AppButton></div>
      </div>
      <AppButton v-else icon="key" class="spc__btn spc__btn--o" variant="secondary" @click="asking = true">{{ t('own.support.request') }}</AppButton>
    </template>
  </section>
</template>

<style scoped>
.spc { display: grid; gap: 10px; padding: 16px 20px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--shape-surface); }
.spc h2 { margin: 0; color: var(--color-text-muted); font: 600 10px var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; }
.spc__big { margin: 0; font: 400 24px/1.2 var(--font-display); }
.spc__text { margin: 0; color: var(--color-text-muted); font-size: var(--text-sm); }
.spc__tags { display: flex; flex-wrap: wrap; gap: 8px; }
.spc__tag { padding: 3px 12px; border-radius: var(--shape-control); background: var(--color-surface-sunken); font-size: var(--text-xs); font-weight: 600; }
.spc__tag--ok { background: var(--color-success-subtle); color: var(--color-success); }
.spc__tag--warn { background: var(--color-warning-subtle); color: var(--color-warning); }
.spc__form { display: grid; gap: 8px; }
.spc__row { display: flex; gap: 8px; flex-wrap: wrap; }
.spc__btn.spc__btn { justify-self: start; border-radius: var(--shape-control); font: 500 var(--text-sm) var(--font-sans); white-space: nowrap; }
</style>
