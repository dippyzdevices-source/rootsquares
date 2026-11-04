<script setup lang="ts">
import { computed } from 'vue'

// Logo mark (final), design v4 export/screens.md "Logo mark (final)": an ink square outline (rx 3, stroke 2.2) with a brass stem hanging from the top edge
// and forking downward inside the box, like roots. Nothing outside the square. Sizes: 16 favicon, 20 console (minimum for the wordmark), 24 marketing,
// 32 footer and auth. The wordmark (lowercase, heading font) shows only from 20px up; its size is 0.8 of the mark (the design's Specs sheet).
const props = withDefaults(defineProps<{ size?: number; text?: string }>(), { size: 24, text: 'rootsquares' })
const showText = computed(() => props.size >= 20 && !!props.text)
</script>

<template>
  <span class="rs-wordmark rs-row bs-row" :style="{ fontSize: `${size * 0.8}px`, gap: '8px', flexWrap: 'nowrap' }">
    <svg :width="size" :height="size" viewBox="0 0 24 24" aria-hidden="true" style="flex: none">
      <rect x="3" y="3" width="18" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="2.2" />
      <path d="M12 4v9M12 9l-4 3M12 9l4 3" fill="none" stroke="var(--color-brass)" stroke-width="2.2" stroke-linecap="round" />
    </svg><template v-if="showText">{{ text }}</template>
  </span>
</template>
