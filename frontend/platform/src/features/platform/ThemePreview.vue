<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { THEME_COLORS } from '@/themes/colors'
import type { ThemeDef, ThemeMode } from '@rootsquares/ui/themes'
import ThemePreviewMain from './ThemePreviewMain.vue'

// Mini site preview of the theme page (design v4 screen 9b, screens/J.jsx `Preview`): the theme's navigation shell (top bar, masthead, two-row tabs, bottom dock,
// left or right sidebar), a hero, and the events in the layout of its first kit (rows, cards, timeline, ledger, bento). Sample words, not the square's.
// Beyond the design (W10-R11): `mode` (light or dark palette), `device` (phone = narrow: sidebars fold into a bar, one column) and `zoom` (the sketch is drawn
// in small units and enlarged, so the same markup serves the page and the full-size dialog).
const props = withDefaults(defineProps<{ theme: ThemeDef; name: string; mode?: ThemeMode; device?: 'desktop' | 'phone'; zoom?: number }>(), { mode: 'light', device: 'desktop', zoom: 1.3 })
const { t } = useI18n()

const c = computed(() => THEME_COLORS[props.theme.id]![props.mode])
const bg = computed(() => c.value.bg)
const ink = computed(() => c.value.ink)
const ac = computed(() => c.value.accent)
const mute = computed(() => ink.value + 'b3')
const ln = computed(() => ink.value + '26')
const sf = computed(() => ink.value + '0d')
const narrow = computed(() => props.device === 'phone')
// A sidebar theme on a phone shows its bar header instead (the real site also folds below 860 px).
const shell = computed(() => (narrow.value && (props.theme.shell === 'side' || props.theme.shell === 'right') ? 'bar' : props.theme.shell))
const nav = computed(() => [t('themes.preview.events'), t('themes.preview.members'), t('themes.preview.about')])
const label = computed(() => t('themes.preview.label', { theme: props.theme.name, shell: props.theme.shellLabel, colour: props.theme.colour }))
const frame = computed(() => ({ zoom: props.zoom, maxWidth: narrow.value ? Math.round(427 / props.zoom) + 'px' : undefined, margin: narrow.value ? '0 auto' : undefined }))
const stageHeight = computed(() => (narrow.value ? '420px' : '300px'))
</script>

<template>
  <div class="tp-pv" role="img" :aria-label="label" :style="frame">
    <div class="tp-pv-u"><i /><i /><i /><span>{{ name.toLowerCase().replace(/[^a-z0-9]+/g, '-') }}.rootsquares.com</span></div>
    <div :style="{ background: bg, color: ink, display: 'flex', flexDirection: 'column', height: stageHeight, overflow: 'hidden' }">
      <!-- Sidebars: the sidebar and the main part side by side -->
      <div v-if="shell === 'side' || shell === 'right'" :style="{ display: 'flex', flex: 1, minHeight: 0, flexDirection: shell === 'right' ? 'row-reverse' : 'row' }">
        <aside :style="{ width: '78px', padding: '12px 10px', display: 'grid', gap: '8px', alignContent: 'start', borderInlineEnd: shell === 'right' ? '0' : '1px solid ' + ln, borderInlineStart: shell === 'right' ? '1px solid ' + ln : '0', background: sf, fontSize: '8.5px', color: mute }">
          <b class="tpv-logo"><i :style="{ background: ac }" />{{ name }}</b>
          <span v-for="(n, i) in nav" :key="n" :style="i === 0 ? { color: ac, fontWeight: 600 } : undefined">{{ n }}</span>
        </aside>
        <div :style="{ flex: 1, minWidth: 0, overflow: 'hidden' }"><ThemePreviewMain :theme="theme" :mode="mode" :narrow="narrow" /></div>
      </div>

      <template v-else>
        <!-- Header by shell -->
        <div v-if="shell === 'dock'" :style="{ display: 'flex', justifyContent: 'space-between', padding: '8px 14px' }"><b class="tpv-logo"><i :style="{ background: ac }" />{{ name }}</b><span class="tpv-btn" :style="{ background: ac, color: bg }">{{ t('themes.preview.join') }}</span></div>
        <div v-else-if="shell === 'mast'" :style="{ display: 'grid', justifyItems: 'center', gap: '6px', padding: '10px 14px 8px', borderBottom: '1px solid ' + ln }">
          <span :style="{ font: '500 16px var(--font-display)', letterSpacing: '.04em' }">{{ name }}</span>
          <span v-if="!narrow" :style="{ display: 'flex', gap: '10px', fontSize: '8.5px', color: mute }"><span v-for="n in nav" :key="n">{{ n }}</span></span>
          <span v-else :style="{ fontSize: '8.5px', color: mute }">☰ {{ t('themes.preview.menu') }}</span>
        </div>
        <template v-else-if="shell === 'tabs'">
          <div :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 14px' }"><b class="tpv-logo"><i :style="{ background: ac }" />{{ name }}</b><span class="tpv-btn" :style="{ background: ac, color: bg }">{{ t('themes.preview.join') }}</span></div>
          <div :style="{ display: 'flex', gap: '14px', padding: '0 14px', borderBottom: '1px solid ' + ln, fontSize: '8.5px' }">
            <span v-for="(n, i) in nav" :key="n" :style="{ padding: '4px 0', borderBottom: i === 0 ? '2px solid ' + ac : '2px solid transparent', color: i === 0 ? ink : mute }">{{ n }}</span>
          </div>
        </template>
        <div v-else :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 14px', background: ac, color: bg }">
          <b :style="{ fontFamily: 'var(--font-display)', fontSize: '12px', fontWeight: 600 }">{{ name }}</b>
          <span v-if="!narrow" :style="{ display: 'flex', gap: '10px', fontSize: '8.5px' }"><span v-for="n in nav" :key="n">{{ n }}</span></span>
          <span v-else :style="{ fontSize: '11px' }" aria-hidden="true">☰</span>
        </div>

        <div :style="{ flex: 1, minWidth: 0, overflow: 'hidden' }"><ThemePreviewMain :theme="theme" :mode="mode" :narrow="narrow" /></div>

        <div v-if="shell === 'dock'" :style="{ margin: '0 auto 10px', display: 'flex', gap: '14px', padding: '6px 14px', borderRadius: '99px', background: ink, color: bg, fontSize: '8.5px' }"><span v-for="n in nav" :key="n">{{ n }}</span></div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.tpv-logo { display: flex; align-items: center; gap: 5px; font-family: var(--font-display); font-size: 12px; font-weight: 600; }
.tpv-logo i { width: 12px; height: 12px; border-radius: 3px; display: block; }
.tpv-btn { padding: 3px 8px; border-radius: 4px; font-size: 8.5px; font-weight: 500; }
</style>
