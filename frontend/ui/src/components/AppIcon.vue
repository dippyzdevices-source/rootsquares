<script setup lang="ts">
import { computed } from 'vue'
import { ICON_PATHS } from './icons'

// Mirrors design/components/core/Icon.jsx
// sun / moon are not in the design's icon set; standard 24px stroke paths added here (see MISSING.md).
const EXTRA: Record<string, string> = {
  sun: 'M12 16a4 4 0 100-8 4 4 0 000 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  bell: 'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0', // "Needs attention" in the admin side bar (W25-R33)
  'chevron-left': 'm15 18-6-6 6-6', // mirror of chevron-right (theme preview dialog, W10-R11)
  // Platform v3 extension screens (design/rootsquares-platform-v2/screens/D.jsx), names added for the new components:
  phone: 'M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM11 18h2',
  tablet: 'M5 3h14v18H5zM11 18h2',
  desk: 'M3 4h18v12H3zM8 20h8M12 16v4',
  out: 'M10 5H5v14h5M14 8l4 4-4 4M18 12H9',
  life: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6M5.6 5.6l3.4 3.4M15 15l3.4 3.4M18.4 5.6L15 9M9 15l-3.4 3.4',
  key: 'M14 10a4 4 0 1 0-3.9 4H12l1 1h2l1 1h2v-2l-3-3',
  eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13',
  refresh: 'M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6',
  'move-up': 'M12 19V5M6 11l6-6 6 6',
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z', // Modules (portal nav, design v4 screens/I.jsx CN list)
  undo: 'M3 7v6h6M3 13a9 9 0 1 0 3-6.7', // Discard changes (W25-R54)
  send: 'M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z', // Send instructions, Allow access (W25-R40)
  external: 'M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6', // opens in a new tab
  ban: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M5.6 5.6l12.8 12.8', // Suspend, End access now
  'move-down': 'M12 5v14M6 13l6 6 6-6', // Brass screens icon (screens/A.jsx), not in the earlier icon set
}
const props = withDefaults(defineProps<{ name: string; size?: number; label?: string; strokeWidth?: number }>(), { size: 20, strokeWidth: 1.5 })
const d = computed(() => ICON_PATHS[props.name] ?? EXTRA[props.name] ?? ICON_PATHS.info)
</script>

<template>
  <svg
    class="rs-icon"
    :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    :stroke-width="strokeWidth" stroke-linecap="round" stroke-linejoin="round"
    :role="label ? 'img' : undefined" :aria-label="label" :aria-hidden="label ? undefined : true"
  ><path :d="d" /></svg>
</template>
