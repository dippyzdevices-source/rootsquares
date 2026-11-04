<script setup lang="ts">
import { useTheme } from '../../composables/useTheme'

const { theme, setTheme } = useTheme()

function toggle() {
  setTheme(theme.value === 'dark' ? 'light' : 'dark')
}
</script>

<template>
  <button
    type="button"
    class="ds-theme-toggle ds-scope"
    :aria-label="theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
    :title="theme === 'dark' ? 'Light theme' : 'Dark theme'"
    @click="toggle"
  >
    <svg
      v-if="theme === 'dark'"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 3v1.5M12 19.5V21M4.6 4.6l1.06 1.06M18.34 18.34l1.06 1.06M3 12h1.5M19.5 12H21M4.6 19.4l1.06-1.06M18.34 5.66l1.06-1.06" />
    </svg>
    <svg
      v-else
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79Z" />
    </svg>
    {{ theme === 'dark' ? 'Light' : 'Dark' }}
  </button>
</template>
