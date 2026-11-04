<script setup lang="ts">
import { computed } from 'vue'
import { squareProfile } from '../../services/squareConfig'
import { useTheme } from '../../composables/useTheme'

// The square's mark: its uploaded logo (W6-R53), else its first letter in a ring. Stands where bca-oslo showed its own logo (rootsquares W6-R36).
// A square can have two logos (W6-R65): one for light backgrounds, one for dark ones. The dark one is used where the background is always dark
// (the footer: `onDark`) and in dark mode; either one stands in for a missing other. The letter takes the colour of the text around it.
// `size` is the height; a logo keeps its own shape (square, round or wide) and is never stretched or cut (W6-R67).
const props = withDefaults(defineProps<{ size?: number; onDark?: boolean }>(), { size: 40, onDark: false })
const { theme } = useTheme()
const letter = computed(() => (squareProfile.name.trim().charAt(0) || '·').toUpperCase())
const box = computed(() => ({ width: `${props.size}px`, height: `${props.size}px`, fontSize: `${Math.round(props.size * 0.5)}px` }))
const logoBox = computed(() => ({ height: `${props.size}px`, width: 'auto', maxWidth: `${props.size * 4}px` }))
const logoSrc = computed(() => {
  const { logoUrl, logoDarkUrl } = squareProfile
  const dark = props.onDark || theme.value === 'dark'
  return (dark ? logoDarkUrl || logoUrl : logoUrl || logoDarkUrl) || ''
})
</script>

<template>
  <img v-if="logoSrc" class="square-logo" :src="logoSrc" alt="" :style="logoBox" />
  <span v-else class="square-mark" :style="box" aria-hidden="true">{{ letter }}</span>
</template>

<style scoped>
.square-logo {
  display: inline-block;
  flex: none;
  object-fit: contain;
}
.square-mark {
  display: inline-grid;
  place-items: center;
  flex: none;
  border: 1.5px solid currentColor;
  border-radius: 50%;
  font-family: var(--ds-font-display, inherit);
  font-weight: 600;
  line-height: 1;
}
</style>
