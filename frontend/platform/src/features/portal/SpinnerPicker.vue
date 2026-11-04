<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import { SPINNER_RECOMMENDED } from '@/themes/lookPresets'
import { SPINNER_ART, SPINNER_OCCASIONS } from '@/themes/spinnerSets'

// "Spinners to keep" (W18-R28, R29, laid out as the Theme Redesign design in W18-R30), in the Spinners tab of the Theme page: the 50 spinners (the festival nine and the others of the Spinner Sets design
// design), one tab per occasion, each spinner drawn and moving and a toggle. The occasions that suit the square's kind of group come first and carry "Suggested". The owner keeps any
// number; the square's loading screens use the kept ones (a different one each time when several), or the nine of the festival set when none is kept. The previews use the platform's own colours
// and the design's sizes (24, 40, 56, 96 px); on the square a spinner takes the colours of the square's theme.
const props = defineProps<{ modelValue: string[]; groupType?: string | null; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [ids: string[]] }>()
const { t } = useI18n()

const SIZES = [24, 40, 56, 96] // the sizes of the Spinner Sets design
const size = ref(56)

const kept = computed(() => new Set(props.modelValue))
const suggested = computed(() => SPINNER_RECOMMENDED[props.groupType ?? 'cultural'] ?? SPINNER_RECOMMENDED.cultural)
const sets = computed(() => {
  const all = SPINNER_OCCASIONS.map((o) => ({ ...o, items: SPINNER_ART.filter((a) => a.set === o.name), suggested: suggested.value.includes(o.name) }))
  return [...all.filter((s) => s.suggested), ...all.filter((s) => !s.suggested)]
})
const tab = ref(0)
const cur = computed(() => sets.value[Math.min(tab.value, sets.value.length - 1)])
const curIds = computed(() => cur.value.items.map((a) => a.id))
const allKept = computed(() => curIds.value.every((id) => kept.value.has(id)))
const keptIn = (ids: string[]) => ids.filter((id) => kept.value.has(id)).length

function toggle(id: string) {
  emit('update:modelValue', kept.value.has(id) ? props.modelValue.filter((x) => x !== id) : [...props.modelValue, id])
}
function toggleSet() {
  const ids = curIds.value
  emit('update:modelValue', allKept.value ? props.modelValue.filter((x) => !ids.includes(x)) : [...props.modelValue, ...ids.filter((id) => !kept.value.has(id))])
}
</script>

<template>
  <div class="sp" :style="{ '--sz': size + 'px' }">
    <div class="sp-top">
      <span class="sp-count" role="status"><b>{{ modelValue.length }}</b> {{ t('portal.theme.look.spinnersKeptWord') }}</span>
      <AppButton v-if="modelValue.length" variant="secondary" size="sm" icon="x" :disabled="disabled" @click="emit('update:modelValue', [])">{{ t('portal.theme.look.spinnersNone') }}</AppButton>
      <span class="sp-size" role="group" :aria-label="t('portal.theme.look.spinnersSize')">
        <button v-for="s in SIZES" :key="s" type="button" class="sp-chip" :aria-pressed="size === s" @click="size = s">{{ s }}px</button>
      </span>
    </div>

    <div class="sp-tabs" role="group" :aria-label="t('portal.theme.look.spinnersOccasion')">
      <button v-for="(s, i) in sets" :key="s.name" type="button" class="sp-chip" :aria-pressed="i === tab" @click="tab = i">
        {{ s.name }}<small v-if="keptIn(s.items.map((a) => a.id))">{{ keptIn(s.items.map((a) => a.id)) }}</small><em v-if="s.suggested">{{ t('portal.theme.look.spinnersSuggested') }}</em>
      </button>
    </div>

    <div class="sp-row">
      <small class="bs-mute">{{ cur.blurb }}</small>
      <AppButton variant="secondary" size="sm" :icon="allKept ? 'x' : 'check'" :disabled="disabled" @click="toggleSet">{{ t(allKept ? 'portal.theme.look.spinnersSetNone' : 'portal.theme.look.spinnersSetAll', { n: curIds.length }) }}</AppButton>
    </div>

    <div class="sp-grid" role="group" :aria-label="cur.name">
      <button v-for="a in cur.items" :key="a.id" type="button" class="sp-tile" :aria-pressed="kept.has(a.id)" :disabled="disabled" :title="a.desc" @click="toggle(a.id)">
        <span class="sp-stage"><span class="sp-art rs-spinner-art" aria-hidden="true" v-html="a.svg" /></span>
        <span class="sp-cap"><span class="sp-nm"><b>{{ a.name }}</b><code>{{ a.id }}</code></span><small>{{ a.desc }}</small></span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.sp { display: grid; gap: 12px; }
.sp-top { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.sp-count { font-size: var(--text-sm); }
.sp-count b { font: 500 var(--text-xl) var(--font-sans); }
.sp-size { margin-left: auto; display: inline-flex; gap: 6px; flex-wrap: wrap; }
.sp-tabs { display: flex; flex-wrap: wrap; gap: 6px; }
.sp-row { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.sp-row small { font-size: var(--text-xs); }
.sp-link { border: 0; background: none; padding: 0; color: var(--color-link, var(--color-primary)); font-size: var(--text-xs); text-decoration: underline; cursor: pointer; }
.sp-link:disabled { cursor: default; opacity: 0.55; }
.sp-chip { display: inline-flex; align-items: center; gap: 6px; min-height: 30px; padding: 0 12px; border: 1px solid var(--color-border-strong); border-radius: 999px; background: var(--color-surface); color: var(--color-text); font-size: var(--text-xs); cursor: pointer; }
.sp-chip small { font-size: 0.68rem; color: var(--color-text-muted); }
.sp-chip em { font-style: normal; font-size: 0.65rem; font-weight: 600; padding: 1px 7px; border-radius: 999px; background: var(--color-brass-subtle); color: var(--color-brass-text); }
.sp-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
@media (max-width: 560px) { .sp-grid { grid-template-columns: 1fr; } }
.sp-tile { position: relative; display: grid; grid-template-rows: auto 1fr; padding: 0; overflow: hidden; border: 1px solid var(--color-border-strong); border-radius: 12px; background: var(--color-surface); color: var(--color-text); text-align: start; font: inherit; cursor: pointer; }
.sp-tile:hover { border-color: var(--color-brass); }
.sp-stage { display: grid; place-items: center; min-height: calc(var(--sz) + 72px); background: #f8f3e9; border-bottom: 1px solid var(--color-border); }
.sp-cap { display: grid; gap: 3px; padding: 10px 14px 12px; align-content: start; }
.sp-nm { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.sp-nm b { font: 500 var(--text-lg) var(--font-sans); }
.sp-nm code { font-size: 0.68rem; color: var(--color-text-muted); }
.sp-cap small { font-size: var(--text-xs); color: var(--color-text-muted); line-height: 1.45; }
.sp-tile[aria-pressed='true']::after { content: '✓'; position: absolute; top: 8px; right: 12px; font-size: 0.8rem; font-weight: 700; color: var(--color-brass-text); }
/* The design's own colours (Spinner Sets: terracotta, saffron, teal on warm paper), the same whatever the platform's theme; on a square the spinner takes that square's colours. */
.sp-art { width: var(--sz); height: var(--sz); align-items: center; justify-content: center; --c1: oklch(0.5 0.15 35); --c2: oklch(0.74 0.14 75); --c3: oklch(0.52 0.09 190); --ink: #2a211a; --bg: #f8f3e9; --track: #dccfb8; }
.sp-chip[aria-pressed='true'], .sp-tile[aria-pressed='true'] { border-color: var(--color-brass); background: var(--color-brass-subtle); box-shadow: inset 0 0 0 1px var(--color-brass); }
.sp-tile:disabled { cursor: default; }
.sp-chip:focus-visible, .sp-tile:focus-visible, .sp-link:focus-visible { outline: 2px solid var(--color-focus, var(--color-primary)); outline-offset: 2px; }
</style>
