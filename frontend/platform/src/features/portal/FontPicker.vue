<script setup lang="ts">
// One font of the owner's own choice (W25-R63): a closed row with the chosen family (or "the pair's"), and a panel to search the Google Fonts catalogue by name, category and script.
// It sends a plain {f, c, w}; the server checks the family again and stores the category and weights itself.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { FONT_CATEGORIES, FONT_SCRIPTS, loadCatalogue, resolveFace, searchFonts, type FontFace, type GoogleFont } from '@/themes/googleFonts'

const props = defineProps<{ label: string; modelValue: FontFace | null | undefined; disabled?: boolean; fallback?: string }>()
const emit = defineEmits<{ 'update:modelValue': [v: FontFace | null] }>()
const { t } = useI18n()

const open = ref(false)
const q = ref('')
const category = ref('')
const script = ref('')
const all = ref<GoogleFont[]>([])
const loading = ref(false)
const failed = ref(false)

async function toggle() {
  open.value = !open.value
  if (open.value && !all.value.length) {
    loading.value = true
    failed.value = false
    try { all.value = await loadCatalogue() } catch { failed.value = true } finally { loading.value = false }
  }
}
const LIMIT = 60
const result = computed(() => searchFonts(all.value, { q: q.value, category: category.value, script: script.value }, LIMIT))
function choose(font: GoogleFont) { emit('update:modelValue', resolveFace(font)); open.value = false }
function clear() { emit('update:modelValue', null); open.value = false }
const scriptName = (s: string) => { const w = s.replace('-', ' '); return w.charAt(0).toUpperCase() + w.slice(1) }
const catLabel = (c: string) => t(`portal.theme.look.cat_${c.replace('-', '_')}`)
</script>

<template>
  <div class="fp">
    <span class="rs-label">{{ label }}</span>
    <div class="fp-row">
      <span class="fp-cur">{{ modelValue ? modelValue.f : (fallback ?? t('portal.theme.look.pickerPair')) }}<small v-if="modelValue">{{ catLabel(modelValue.c) }}</small></span>
      <span class="fp-btns">
        <AppButton variant="secondary" size="sm" :icon="open ? 'x' : 'search'" :disabled="disabled" :aria-expanded="open" @click="toggle">{{ open ? t('portal.theme.look.pickerClose') : t('portal.theme.look.pickerChoose') }}</AppButton>
        <AppButton v-if="modelValue" variant="ghost" size="sm" icon="undo" :disabled="disabled" @click="clear">{{ t('portal.theme.look.pickerClear') }}</AppButton>
      </span>
    </div>
    <div v-if="open" class="fp-panel">
      <input v-model="q" class="rs-input" type="search" :placeholder="t('portal.theme.look.pickerSearch')" :aria-label="t('portal.theme.look.pickerSearch')" autocomplete="off" />
      <div class="tp-chips" role="group" :aria-label="t('portal.theme.look.pickerKind')">
        <button type="button" :aria-pressed="!category" @click="category = ''">{{ t('portal.theme.look.cat_all') }}</button>
        <button v-for="c in FONT_CATEGORIES" :key="c" type="button" :aria-pressed="category === c" @click="category = category === c ? '' : c">{{ catLabel(c) }}</button>
      </div>
      <label class="fp-script"><span class="rs-label">{{ t('portal.theme.look.pickerScript') }}</span>
        <select v-model="script" class="rs-input">
          <option value="">{{ t('portal.theme.look.pickerAnyScript') }}</option>
          <option v-for="s in FONT_SCRIPTS" :key="s" :value="s">{{ scriptName(s) }}</option>
        </select>
      </label>
      <p class="bs-mute fp-count" role="status">{{ loading ? t('portal.theme.look.pickerLoading') : failed ? t('portal.theme.look.pickerFailed') : t('portal.theme.look.pickerCount', { n: result.total }, result.total) }}<template v-if="!loading && !failed && result.total > LIMIT"> · {{ t('portal.theme.look.pickerMore', { n: LIMIT }) }}</template></p>
      <ul class="fp-list">
        <li v-for="f in result.shown" :key="f.f">
          <button type="button" class="fp-item" :aria-pressed="modelValue?.f === f.f" @click="choose(f)"><b>{{ f.f }}</b><small>{{ catLabel(f.c) }}</small></button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.fp { display: grid; gap: 6px; }
.fp-row { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; justify-content: space-between; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--shape-field); background: var(--color-surface-sunken); }
.fp-cur { display: grid; flex: 1 1 120px; min-width: 0; font-size: var(--text-sm); overflow-wrap: anywhere; }
.fp-cur small { color: var(--color-text-muted); font-size: var(--text-xs); }
.fp-btns { display: flex; gap: 8px; flex-wrap: wrap; }
.fp-panel { display: grid; gap: 10px; padding: 12px; border: 1px solid var(--color-border-strong); border-radius: var(--shape-inner); background: var(--color-surface); }
.fp-script { display: grid; gap: 4px; max-width: 280px; }
.fp-count { margin: 0; font-size: var(--text-xs); }
.fp-list { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 6px; max-height: 280px; overflow: auto; padding-right: 4px; }
.fp-item { display: grid; width: 100%; min-height: 44px; padding: 6px 10px; text-align: start; border: 1px solid var(--color-border); border-radius: var(--shape-inner); background: var(--color-surface); cursor: pointer; }
.fp-item:hover { border-color: var(--color-brass); }
.fp-item[aria-pressed='true'] { border-color: var(--color-brass); background: var(--color-brass-subtle); box-shadow: inset 0 0 0 1px var(--color-brass); }
.fp-item b { font-weight: 500; font-size: var(--text-sm); overflow-wrap: anywhere; }
.fp-item small { color: var(--color-text-muted); font-size: var(--text-xs); }
.fp-item:focus-visible { outline: 2px solid var(--color-focus, var(--color-primary)); outline-offset: 2px; }
</style>
