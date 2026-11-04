<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { THEME_COLORS } from '@/themes/colors'
import type { ThemeDef, ThemeMode } from '@rootsquares/ui/themes'

// Hero and the events list of the theme preview (design v4 screen 9b, screens/J.jsx `Preview`): the list follows the theme's first kit.
const props = withDefaults(defineProps<{ theme: ThemeDef; mode?: ThemeMode; narrow?: boolean }>(), { mode: 'light', narrow: false })
const { t } = useI18n()
const c = computed(() => THEME_COLORS[props.theme.id]![props.mode])
const bg = computed(() => c.value.bg)
const ac = computed(() => c.value.accent)
const a2 = computed(() => c.value.g)
const mute = computed(() => c.value.ink + 'b3')
const ln = computed(() => c.value.ink + '26')
const sf = computed(() => c.value.ink + '0d')
const masthead = computed(() => props.theme.shell === 'mast')
const bento = computed(() => props.theme.look.includes('bento'))
const kind = computed<'cards' | 'timeline' | 'ledger' | 'rows'>(() => {
  const l = props.theme.look
  if (l.startsWith('cards') || (bento.value && !l.startsWith('ledger'))) return 'cards'
  if (l === 'timeline') return 'timeline'
  if (l.startsWith('ledger')) return 'ledger'
  return 'rows'
})
const idx = [0, 1, 2]
</script>

<template>
  <div>
    <div :style="{ display: 'grid', gap: '6px', padding: '14px 14px 8px', justifyItems: masthead ? 'center' : 'start', textAlign: masthead ? 'center' : 'start' }">
      <span :style="{ fontSize: '7.5px', letterSpacing: '.12em', textTransform: 'uppercase', color: a2 }">{{ t('themes.preview.next') }}</span>
      <span :style="{ font: '500 20px/1.05 var(--font-display)' }">{{ t('themes.preview.title1') }}<br />{{ t('themes.preview.title2') }}</span>
      <span :style="{ background: ac, color: bg, padding: '3px 8px', borderRadius: '4px', fontSize: '8.5px', fontWeight: 500 }">{{ t('themes.preview.join') }}</span>
    </div>

    <div v-if="kind === 'cards'" :style="{ display: 'grid', gridTemplateColumns: narrow ? '1fr' : bento ? '2fr 1fr' : '1fr 1fr 1fr', gap: '6px', padding: '0 14px' }">
      <div v-for="i in idx" :key="i" :style="{ background: sf, border: '1px solid ' + ln, borderRadius: '5px', height: i === 0 && bento && !narrow ? '54px' : '40px', padding: '6px', fontSize: '8px', gridRow: i === 0 && bento && !narrow ? 'span 2' : undefined }">
        <div :style="{ width: '60%', height: '5px', background: i === 0 ? ac : ln, borderRadius: '2px', marginBottom: '4px' }" />
        <div :style="{ width: '85%', height: '4px', background: ln, borderRadius: '2px' }" />
      </div>
    </div>
    <div v-else-if="kind === 'timeline'" :style="{ padding: '0 14px 0 20px', display: 'grid', gap: '8px', borderInlineStart: '1px solid ' + ln, margin: '0 14px' }">
      <div v-for="i in idx" :key="i" :style="{ position: 'relative', fontSize: '8.5px', paddingInlineStart: '8px' }">
        <i :style="{ position: 'absolute', left: '-25px', top: '2px', width: '8px', height: '8px', borderRadius: '50%', background: i === 0 ? ac : bg, border: '1.5px solid ' + ac }" />
        <b :style="{ fontWeight: 500 }">{{ t('themes.preview.event', { n: i + 1 }) }}</b><br /><span :style="{ color: mute }">{{ t('themes.preview.when') }}</span>
      </div>
    </div>
    <div v-else-if="kind === 'ledger'" :style="{ padding: '0 14px', fontSize: '8.5px' }">
      <div v-for="i in idx" :key="i" :style="{ display: 'grid', gridTemplateColumns: '34px 1fr auto', gap: '8px', padding: '5px 0', borderTop: '1px solid ' + ln, fontFamily: 'var(--font-mono)' }">
        <span :style="{ color: a2 }">12.10</span><span :style="{ fontFamily: 'var(--font-sans)' }">{{ t('themes.preview.event', { n: i + 1 }) }}</span><span :style="{ color: mute }">{{ t('themes.preview.free') }}</span>
      </div>
    </div>
    <div v-else :style="{ padding: '0 14px' }">
      <div v-for="i in idx" :key="i" :style="{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderTop: '1px solid ' + ln, fontSize: '8.5px' }">
        <span><b :style="{ fontWeight: 500 }">{{ t('themes.preview.event', { n: i + 1 }) }}</b><br /><span :style="{ color: mute }">{{ t('themes.preview.whenHall') }}</span></span>
        <span :style="{ color: a2, fontWeight: 600 }">→</span>
      </div>
    </div>
  </div>
</template>
