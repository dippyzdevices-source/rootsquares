<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Mirrors design/components/forms/ColorPicker.jsx, including the AA contrast checks.
const props = withDefaults(defineProps<{ modelValue: string; background?: string; presets?: string[] }>(), {
  background: '#ffffff',
  presets: () => ['#1d6a78', '#8a2f2f', '#2c5aa0', '#3b7a3b', '#b4781e', '#5b3a8a'],
})
const emit = defineEmits<{ 'update:modelValue': [v: string] }>()
const { t } = useI18n()

const hex = (v: string) => {
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec((v || '').trim())
  if (!m) return null
  let h = m[1]!
  if (h.length === 3) h = h.split('').map((c) => c + c).join('')
  return '#' + h.toLowerCase()
}
const lum = (h: string) => {
  const n = parseInt(h.slice(1), 16)
  const c = [n >> 16, (n >> 8) & 255, n & 255].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) })
  return c[0]! * 0.2126 + c[1]! * 0.7152 + c[2]! * 0.0722
}
const ratio = (a: string, b: string) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05) }

const cur = computed(() => hex(props.modelValue) || '#000000')
const fg = computed(() => (ratio(cur.value, '#ffffff') >= ratio(cur.value, '#1a1a1a') ? '#ffffff' : '#1a1a1a'))
const checks = computed(() => [
  { title: t('color.textOnColour'), fg: fg.value, bg: cur.value, r: ratio(fg.value, cur.value) },
  { title: t('color.colourOnPage'), fg: cur.value, bg: props.background, r: ratio(cur.value, props.background) },
])
</script>

<template>
  <div class="rs-stack">
    <div class="rs-label">{{ t('color.label') }}</div>
    <div class="rs-swatches" role="group" :aria-label="t('color.label')">
      <button v-for="p in presets" :key="p" type="button" class="rs-swatch" :style="{ background: p }" :aria-pressed="hex(p) === cur" :aria-label="p" @click="emit('update:modelValue', p)">
        <AppIcon v-if="hex(p) === cur" name="check" :style="{ color: ratio(p, '#ffffff') > 3 ? '#fff' : '#1a1a1a' }" />
      </button>
      <input type="color" :aria-label="t('color.custom')" :value="cur" class="rs-swatch" style="padding: 2px; background: var(--color-surface)" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)">
    </div>
    <input class="rs-input" :aria-label="t('color.hex')" :value="modelValue" :aria-invalid="hex(modelValue) ? undefined : true" maxlength="7" style="font-family: ui-monospace, monospace" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)">
    <div class="rs-contrast">
      <div v-for="c in checks" :key="c.title" :style="{ background: c.bg, color: c.fg }">
        <b>{{ c.title }}</b>
        <span class="rs-pass"><AppIcon :name="c.r >= 4.5 ? 'circle-check' : 'alert'" :size="16" />{{ c.r >= 4.5 ? t('color.pass') : t('color.fail') }} · {{ c.r.toFixed(1) }}:1</span>
      </div>
    </div>
  </div>
</template>
