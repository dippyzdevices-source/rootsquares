<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { THEME_COLORS } from '@/themes/colors'
import { useUiStore } from '@rootsquares/ui/stores/ui'
import type { ThemeDef } from '@rootsquares/ui/themes'

// "Coming up" (W10-R8): themes that are built but not offered yet. Shown under the offered list, not selectable.
const { t } = useI18n()
const ui = useUiStore()
defineProps<{ themes: ThemeDef[] }>()
const swatches = (id: string) => { const c = THEME_COLORS[id]?.[ui.mode]; return c ? [c.bg, c.ink, c.accent] : [] }
</script>

<template>
  <section v-if="themes.length" class="tc-box" :aria-label="t('themes.coming')">
    <h3 class="tc-h">{{ t('themes.coming') }} <small>{{ themes.length }}</small></h3>
    <p class="tc-hint">{{ t('themes.comingHint') }}</p>
    <ul class="tc-list">
      <li v-for="th in themes" :key="th.id" class="tc-item">
        <span class="tc-sw"><b v-for="c in swatches(th.id)" :key="c" :style="{ background: c }" /></span>
        <span class="tc-name">{{ th.name }}<small>{{ th.shellLabel }} · {{ th.colour }}</small></span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.tc-box { display: grid; gap: 6px; margin-top: 14px; padding: 12px; border: 1px solid var(--color-brass); border-radius: 8px; background: var(--color-brass-subtle); }
.tc-h { margin: 0; font: 500 0.72rem/1.2 var(--font-sans); letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-brass-text); } /* the Brass eyebrow style */
.tc-h small { color: var(--color-text-muted); font-weight: 400; letter-spacing: 0; }
.tc-hint { margin: 0; font-size: var(--text-xs); color: var(--color-text-muted); }
.tc-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.tc-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border: 1px dashed var(--color-brass); border-radius: 6px; background: var(--color-surface); opacity: 0.85; cursor: default; }
.tc-sw { display: inline-flex; flex: none; }
.tc-sw b { width: 14px; height: 24px; border: 1px solid var(--color-border); }
.tc-name { display: grid; font-size: var(--text-sm); }
.tc-name small { color: var(--color-text-muted); font-size: var(--text-xs); }
</style>
