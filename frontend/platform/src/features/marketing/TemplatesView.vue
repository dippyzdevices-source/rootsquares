<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { startTarget } from '@/features/platform/startFlow'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'
import { useToast } from '@rootsquares/ui/components/useToast'
import { THEMES, type ThemeMode } from '@rootsquares/ui/themes'
import { THEME_COLORS } from '@/themes/colors'
import ThemeFilterBar from '@/features/platform/ThemeFilterBar.vue'
import ThemeComingList from '@/features/platform/ThemeComingList.vue'
import ThemePreviewDialog from '@/features/platform/ThemePreviewDialog.vue'
import ThemePreviewPane from '@/features/platform/ThemePreviewPane.vue'
import { useThemeFilter } from '@/features/platform/themeFilter'

// Mirrors screens/C.jsx (Themes) in design/rootsquares-platform-brass: numbered theme list, mode switch, mini site preview, detail card; strip + sticky bar when narrow.
const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const { push } = useToast()
const { q, shell, filtered, counts, coming } = useThemeFilter()
const mode = ref<ThemeMode>('light')
const device = ref<'desktop' | 'tablet' | 'mobile'>('desktop')
const selectedId = ref<string>(THEMES[0]!.id)
const previewOpen = ref(false)
// The wide page is exactly as tall as the window (no page scroll, marketing.css): the preview takes what the card, the switches and the header leave.
const win = ref({ w: typeof window === 'undefined' ? 1280 : window.innerWidth, h: typeof window === 'undefined' ? 900 : window.innerHeight })
const onResize = () => { win.value = { w: window.innerWidth, h: window.innerHeight } }
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
const clip = computed(() => (win.value.w < 760 ? 740 : Math.max(360, win.value.h - 430)))
const selected = computed(() => THEMES.find((x) => x.id === selectedId.value)!)

const h2r = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))
const mix = (a: string, b: string, k: number) => {
  const x = h2r(a), y = h2r(b)
  return '#' + x.map((v, i) => Math.round(v! * (1 - k) + y[i]! * k).toString(16).padStart(2, '0')).join('')
}
const lum = (h: string) => h2r(h).map((v) => { const s = v! / 255; return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4) }).reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i]!, 0)
const cr = (a: string, b: string) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05) }
const onC = (c: string) => (cr(c, '#ffffff') >= cr(c, '#161411') ? '#ffffff' : '#161411')
function pal(id: string, m: ThemeMode) {
  const c = THEME_COLORS[id]![m]
  const bg = c.bg.toLowerCase(), ink = c.ink.toLowerCase(), ac = c.accent.toLowerCase()
  return { bg, ink, ac, serif: c.serif, mu: mix(ink, bg, 0.3), sf: mix(bg, '#ffffff', m === 'dark' ? 0.05 : 0.5), bd: mix(bg, ink, m === 'dark' ? 0.2 : 0.18), on: onC(ac) }
}
const p = computed(() => pal(selectedId.value, mode.value))
const light = (id: string) => THEME_COLORS[id]!.light

function use() {
  push(t('marketing.templates.chosen', { theme: selected.value.name }), 'success', t('marketing.templates.chosenBody'))
  void router.push(startTarget(!!auth.user, { theme: selected.value.id }))
}
</script>

<template>
  <section class="bt-page">
    <div class="bt-grid">
      <div class="bt-left">
        <div class="bt-head">
          <span class="rs-eyebrow">{{ t('marketing.templates.eyebrow') }}</span>
          <h1 class="bs-d">{{ t('marketing.templates.titleA') }} <em>{{ t('marketing.templates.titleB') }}</em></h1>
          <hr class="rs-rule" />
          <p class="bs-lede" style="font-size: var(--text-base)">{{ t('marketing.templates.lede') }}</p>
        </div>

        <ThemeFilterBar v-model:q="q" v-model:shell="shell" :shown="filtered.length" :counts="counts" />

        <div class="bt-seg bt-only-narrow" role="group" aria-labelledby="mode-label-n">
          <span id="mode-label-n" class="rs-label">{{ t('marketing.templates.mode') }}</span>
          <div>
            <button type="button" :aria-pressed="mode === 'light'" @click="mode = 'light'">{{ t('marketing.templates.light') }}</button>
            <button type="button" :aria-pressed="mode === 'dark'" @click="mode = 'dark'">{{ t('marketing.templates.dark') }}</button>
          </div>
        </div>

        <div class="bt-list bt-only-wide" role="listbox" :aria-label="t('marketing.templates.list')">
          <p v-if="!filtered.length" class="bs-mute" style="padding: 12px">{{ t('themes.none') }}</p>
          <button v-for="th in filtered" :key="th.id" type="button" role="option" :aria-selected="th.id === selectedId" @click="selectedId = th.id">
            <span class="bs-n">{{ String(th.n).padStart(2, '0') }}</span>
            <span class="bt-dots"><i :style="{ background: light(th.id).bg }" /><i :style="{ background: light(th.id).ink }" /><i :style="{ background: light(th.id).accent }" /></span>
            <b>{{ th.name }}</b>
            <AppIcon v-if="th.id === selectedId" name="check" :size="14" />
          </button>
        </div>
        <div class="bt-only-wide bt-coming"><ThemeComingList :themes="coming" /></div>
      </div>

      <div class="bt-right">
        <div class="bt-seg bt-only-wide" role="group" aria-labelledby="mode-label-w">
          <span id="mode-label-w" class="rs-label">{{ t('marketing.templates.mode') }}</span>
          <div>
            <button type="button" :aria-pressed="mode === 'light'" @click="mode = 'light'">{{ t('marketing.templates.light') }}</button>
            <button type="button" :aria-pressed="mode === 'dark'" @click="mode = 'dark'">{{ t('marketing.templates.dark') }}</button>
          </div>
          <span class="rs-label" style="margin-inline-start: 12px">{{ t('marketing.templates.device') }}</span>
          <div>
            <button type="button" :aria-pressed="device === 'desktop'" @click="device = 'desktop'">{{ t('marketing.templates.desktop') }}</button>
            <button type="button" :aria-pressed="device === 'tablet'" @click="device = 'tablet'">{{ t('marketing.templates.tablet') }}</button>
            <button type="button" :aria-pressed="device === 'mobile'" @click="device = 'mobile'">{{ t('marketing.templates.mobile') }}</button>
          </div>
        </div>

        <ThemePreviewPane :theme="selected" :name="t('marketing.templates.pv.org')" :mode="mode" :device="device === 'mobile' ? 'phone' : device" :sketch-zoom="1.8" :clip-height="clip" :extra-height="{ desktop: 300, tablet: 100, phone: 100 }" interactive />

        <div class="bt-strip bt-only-narrow" role="listbox" :aria-label="t('marketing.templates.list')">
          <button v-for="th in filtered" :key="th.id" type="button" role="option" :aria-selected="th.id === selectedId" @click="selectedId = th.id">
            <span class="bt-dots"><i :style="{ background: light(th.id).bg }" /><i :style="{ background: light(th.id).ink }" /><i :style="{ background: light(th.id).accent }" /></span>{{ th.name }}
          </button>
        </div>


        <div class="bt-detail bt-only-wide">
          <div style="display: grid; gap: 4px">
            <b style="font-family: var(--font-heading); font-weight: 600; font-size: var(--text-xl); letter-spacing: -0.015em">{{ selected.name }}</b>
            <span class="bs-mute" style="font-size: var(--text-sm)"><span style="color: var(--color-text); font-weight: 500">{{ t('marketing.templates.suits') }}:</span> {{ selected.suits }}</span>
            <span class="bs-mute" style="font-size: var(--text-xs)">{{ t('marketing.templates.shellIs') }}: {{ selected.shellLabel }} · {{ selected.look }} · {{ selected.display }} / {{ selected.body }} · {{ selected.corners }}<template v-if="selected.mode === 'dark'"> · {{ t('marketing.templates.opensDark') }}</template></span>
            <div class="bs-row" style="margin-top: 4px">
              <span v-for="c in [p.bg, p.ink, p.ac]" :key="c" class="bt-sw"><i :style="{ background: c }" />{{ c }}</span>
            </div>
          </div>
          <div class="bs-row" style="flex-wrap: wrap">
            <AppButton variant="secondary" icon="globe" @click="previewOpen = true">{{ t('marketing.templates.preview') }}</AppButton>
            <AppButton icon="check" @click="use">{{ t('marketing.templates.use') }}</AppButton>
          </div>
        </div>
      </div>
    </div>

    <div class="bt-sticky bt-only-narrow">
      <div>
        <b style="font-weight: 500">{{ selected.name }}</b>
        <div class="bs-mute" style="font-size: var(--text-xs)">{{ selected.suits }}</div>
      </div>
      <AppButton icon="check" @click="use">{{ t('marketing.templates.use2') }}</AppButton>
    </div>
  
    <ThemePreviewDialog v-if="previewOpen" :themes="THEMES" :theme-id="selectedId" :name="t('marketing.templates.pv.org')" can-apply :apply-label="t('marketing.templates.use')" @update:theme-id="(id) => (selectedId = id)" @apply="use" @close="previewOpen = false" />
  </section>
</template>
