<script setup lang="ts">
import { computed } from 'vue'
import { useTheme } from '../../composables/useTheme'

// Light / dark switch for the headers of the themed shells (W9-R5): a 44 px icon button that takes the colour of the header around it.
const { theme, setTheme } = useTheme()
const dark = computed(() => theme.value === 'dark')
</script>

<template>
  <button type="button" class="lt-mode" :aria-label="dark ? 'Switch to light mode' : 'Switch to dark mode'" :title="dark ? 'Light mode' : 'Dark mode'" @click="setTheme(dark ? 'light' : 'dark')">
    <svg v-if="dark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 3v1.5M12 19.5V21M4.6 4.6l1.06 1.06M18.34 18.34l1.06 1.06M3 12h1.5M19.5 12H21M4.6 19.4l1.06-1.06M18.34 5.66l1.06-1.06" />
    </svg>
    <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  </button>
</template>
