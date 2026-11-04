<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Mirrors design/components/platform/ThemeTile.jsx: tenant colours only inside the framed preview; the tile chrome stays rootsquares.
const props = withDefaults(defineProps<{
  name: string
  bg?: string
  ink?: string
  accent?: string
  serif?: boolean
  selected?: boolean
  sample?: string
  cta?: string
}>(), { bg: '#ffffff', ink: '#1a1a1a', accent: '#8a2f2f', sample: 'Welcome', cta: 'Join us' })
defineEmits<{ select: [] }>()

const { t } = useI18n()
const lum = (h: string) => {
  const n = parseInt(h.slice(1), 16)
  const c = [n >> 16, (n >> 8) & 255, n & 255].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) })
  return c[0]! * 0.2126 + c[1]! * 0.7152 + c[2]! * 0.0722
}
const on = computed(() => (lum(props.accent) > 0.4 ? '#1a1a1a' : '#ffffff'))
</script>

<template>
  <button type="button" class="rs-tile" :aria-pressed="!!selected" @click="$emit('select')">
    <div class="rs-tile__prev" :style="{ background: bg, color: ink, fontFamily: serif ? 'Georgia,serif' : 'system-ui,sans-serif' }" aria-hidden="true">
      <header :style="{ background: accent, color: on }">{{ name }}<i :style="{ background: on, opacity: 0.6 }" /></header>
      <div><b>{{ sample }}</b><span style="opacity: 0.7">— — — —</span><u :style="{ background: accent, color: on }">{{ cta }}</u></div>
    </div>
    <div class="rs-row rs-between" style="flex-wrap: nowrap">
      <b>{{ name }}</b>
      <span v-if="selected" class="rs-chip rs-chip--live" style="padding: 2px 8px 2px 6px"><AppIcon name="check" :size="14" />{{ t('common.selected') }}</span>
    </div>
  </button>
</template>
