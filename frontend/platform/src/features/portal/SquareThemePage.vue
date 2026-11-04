<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import ThemePreviewPane from '@/features/platform/ThemePreviewPane.vue'
import ThemePreviewDialog from '@/features/platform/ThemePreviewDialog.vue'
import { ALL_THEMES } from '@rootsquares/ui/themes'
import { ALL_SCHEMES, FONT_PAIRS, SHAPE_PARTS, FEEL_PARTS, presetColours } from '@/themes/lookPresets'
import { SPINNER_ART } from '@/themes/spinnerSets'
import type { ThemeLook } from '@/services/platform'
import { useSquare } from './squareContext'

// Theme page (W19-R3): only the look the public site wears now, and one big way into the Theme Studio (ThemeStudioPage.vue, its own full-window route). Nothing is edited here.
const { t } = useI18n()
const { sq } = useSquare()
const current = computed(() => ALL_THEMES.find((x) => x.id === sq.value?.theme_id))
const o = computed(() => sq.value?.theme_overrides ?? null)
const look = computed<ThemeLook | null>(() => {
  const v = o.value
  return v && (v.colors || v.colors_dark || v.fonts || v.shape || v.feel || v.type) ? { colors: v.colors ? { ...v.colors } : null, colors_dark: v.colors_dark ? { ...v.colors_dark } : null, fonts: v.fonts ?? null, shape: v.shape ? { ...v.shape } : null, feel: v.feel ? { ...v.feel } : null, type: v.type ? JSON.parse(JSON.stringify(v.type)) : null } : null
})
// "Buttons: Pill, Cards: Soft": the part and the chosen option, as the tabs name them
const pick = (parts: { id: string; options: { id: string; label: string }[] }[], c: Record<string, string | undefined>) =>
  parts.filter((x) => c[x.id]).map((x) => `${x.id[0].toUpperCase()}${x.id.slice(1)}: ${x.options.find((o) => o.id === c[x.id])?.label ?? c[x.id]}`).join(', ')
// What the owner has changed on top of the theme, one line each; nothing changed = the theme as designed.
// The ready-made scheme the three colours are, else "my own": the same words as the studio's Colours tab (TS-12)
function schemeName(c: { bg: string; ink: string; acc: string } | null | undefined, mode: 'light' | 'dark'): string {
  if (!c) return t('portal.theme.look.own')
  const hit = ALL_SCHEMES.find((s) => { const p = presetColours(s.id, mode); return !!p && p.bg === c.bg && p.ink === c.ink && p.acc === c.acc })
  return hit?.name ?? t('portal.theme.look.own')
}
// the page, text and accent colours as a chip (the same three bars as the studio's Colours tab)
const chipOf = (c: { bg: string; ink: string; acc: string } | null | undefined): string[] | undefined => (c ? [c.bg, c.ink, c.acc] : undefined)
const parts = computed(() => {
  const v = o.value, c = current.value, dflt = t('portal.theme.landing.themeDefault')
  const side = c?.mode === 'dark' ? 'dark' : 'light'
  const asDesigned = presetColours(sq.value?.theme_id ?? '', side) // the theme's own three colours, for the chip when nothing of the owner's is set
  const rows: { k: string; v: string; chip?: string[] }[] = [
    { k: t('portal.theme.landing.layout'), v: c?.shellLabel ?? '' },
    { k: t('portal.theme.tabColours'), v: v?.colors ? schemeName(v.colors, side) : (c?.colour ?? dflt), chip: chipOf(v?.colors ?? asDesigned) },
  ]
  if (v?.colors_dark) rows.push({ k: t('portal.theme.look.darkTitle'), v: schemeName(v.colors_dark, 'dark'), chip: chipOf(v.colors_dark) })
  rows.push({ k: t('portal.theme.tabFonts'), v: v?.fonts ? (FONT_PAIRS.find((f) => f.id === v.fonts)?.label ?? v.fonts) : (c ? `${c.display} / ${c.body}` : dflt) })
  if (v?.type) rows.push({ k: t('portal.theme.look.typeTitle'), v: [v.type.display && `${t('portal.theme.look.typeHeading')}: ${v.type.display.f}`, v.type.body && `${t('portal.theme.look.typeBody')}: ${v.type.body.f}`, v.type.accent && `${t('portal.theme.look.typeAccent')}: ${v.type.accent}`].filter(Boolean).join(', ') })
  rows.push({ k: t('portal.theme.tabShapes'), v: v?.shape && Object.keys(v.shape).length ? pick(SHAPE_PARTS, v.shape) : dflt })
  rows.push({ k: t('portal.theme.tabFeel'), v: v?.feel && Object.keys(v.feel).length ? pick(FEEL_PARTS, v.feel) : dflt })
  rows.push({ k: t('portal.theme.tabSpinners'), v: v?.spinners?.length ? v.spinners.map((id) => SPINNER_ART.find((a) => a.id === id)?.name ?? id).join(', ') : dflt })
  return rows
})
const fullOpen = ref(false) // the full preview (W19-R5): the old dialog, moved here from the studio; it shows the current theme and look, nothing to apply
const seasons = computed(() => sq.value?.look_seasons?.length ?? 0)
const draft = computed(() => sq.value?.look_draft ?? null)
</script>

<template>
  <div v-if="sq" class="tp tl-page">
    <div class="tp-hd"><h2 class="bs-h2" style="font-size: 32px; margin: 0">{{ t('portal.theme.title') }}</h2><p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('portal.theme.landing.lede', { name: sq.name }) }}</p></div>

    <div class="tl-grid">
      <div v-if="current" class="tl-pv">
        <ThemePreviewPane :theme="current" :name="sq.name" :sketch-zoom="1.5" :look="look" mode="light" device="desktop" :max-height="440" />
        <AppButton variant="secondary" icon="eye" class="tl-full" @click="fullOpen = true">{{ t('portal.theme.fullPreview') }}</AppButton>
      </div>
      <div class="tl-side">
        <p class="tl-kick">{{ t('portal.theme.landing.now') }}</p>
        <h3 class="tl-name">{{ current?.name ?? sq.theme_id }}</h3>
        <dl class="tl-parts">
          <div v-for="p in parts" :key="p.k"><dt>{{ p.k }}</dt><dd :class="{ 'tl-chipv': p.chip }"><i v-if="p.chip" class="tl-sw" aria-hidden="true"><b v-for="c in p.chip" :key="c" :style="{ background: c }" /></i>{{ p.v }}</dd></div>
        </dl>
        <p v-if="seasons || draft" class="bs-mute tl-meta">
          <span v-if="seasons">{{ t('portal.theme.landing.seasons', { n: seasons }, seasons) }}</span><span v-if="seasons && draft"> · </span>
          <span v-if="draft">{{ draft.expired ? t('portal.theme.look.draft.expired') : t('portal.theme.landing.draftOn') }}</span>
        </p>
        <RouterLink :to="`/squares/${sq.id}/theme/studio`" class="tl-go"><AppButton size="lg" icon="palette">{{ t('portal.theme.landing.go') }}</AppButton></RouterLink>
        <p class="bs-mute tl-meta">{{ t('portal.theme.landing.goNote') }}</p>
      </div>
    </div>
    <ThemePreviewDialog v-if="fullOpen && current" :themes="[current]" :theme-id="current.id" :name="sq.name" :look="look" :current-id="sq.theme_id" @close="fullOpen = false" />
  </div>
</template>

<style scoped>
.tl-page { display: grid; gap: 20px; }
.tl-grid { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(280px, 1fr); gap: 28px; align-items: start; }
.tl-pv { min-width: 0; padding: 14px; border: 1px solid var(--color-border); border-radius: var(--shape-surface); background: var(--color-surface-sunken); }
.tl-full { margin-top: 12px; }
/* Same button style as the square page (W23-R28): a pill, capitals, a light outline. */
.tl-full.tl-full { padding: 0 14px; border-radius: var(--shape-control); border-color: var(--color-border); background: var(--color-surface); color: var(--color-text); font: 600 11px var(--font-sans); letter-spacing: 0.1em; text-transform: uppercase; white-space: nowrap; }
.tl-full.tl-full:hover { border-color: var(--color-border); background: var(--color-surface-sunken); }
.tl-side { display: grid; gap: 10px; align-content: start; }
.tl-kick { margin: 0; font: 600 0.7rem/1.2 var(--font-sans); letter-spacing: 0.15em; text-transform: uppercase; color: var(--color-brass-text); }
.tl-name { margin: 0; font: 400 34px/1.1 var(--font-display, var(--font-sans)); }
.tl-meta { margin: 0; font-size: var(--text-sm); }
.tl-parts { display: grid; gap: 6px; margin: 4px 0; }
.tl-parts > div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 7px 0; border-bottom: 1px solid var(--color-border); font-size: var(--text-sm); }
.tl-parts dt { flex: none; color: var(--color-text-muted); }
.tl-chipv { display: inline-flex; gap: 8px; align-items: center; justify-content: flex-end; }
.tl-sw { display: inline-flex; flex: none; border-radius: 99px; overflow: hidden; border: 1px solid var(--color-border-strong); }
.tl-sw b { width: 12px; height: 16px; display: block; }
.tl-parts dd { margin: 0; font-weight: 500; text-align: end; }
.tl-go { display: block; margin-top: 10px; text-decoration: none; }
.tl-go :deep(.rs-btn.rs-btn.rs-btn.rs-btn.rs-btn.rs-btn) { width: 100%; justify-content: center; padding-block: 16px; font-size: 13px; letter-spacing: 0.12em; } /* the one big button: an exception to the 11px of buttons.css (W25-R37) */
@media (max-width: 900px) { .tl-grid { grid-template-columns: 1fr; } }
</style>
