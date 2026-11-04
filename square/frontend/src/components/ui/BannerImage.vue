<script setup lang="ts">
import { ref, watch } from 'vue'

// Renders any uploaded banner (landscape, portrait, or square) with zero cropping —
// object-fit: contain on the real image guarantees no content is ever cut off, and a static
// warm-wash matte (.ds-banner-bg, design-system.css — same texture as the "no photo"
// placeholder below) fills the letterbox/pillarbox space behind it, rather than a blurred
// copy of the photo itself, which looked muddy for portrait/odd-ratio uploads.
const props = defineProps<{
  src: string | null
  alt: string
}>()

const failed = ref(false)

// Reset "failed to load" whenever the image itself changes (e.g. cycling a slider, or
// navigating to a different event) — otherwise a later, perfectly good image would stay
// stuck showing the placeholder left over from an earlier broken one.
watch(
  () => props.src,
  () => {
    failed.value = false
  },
)
</script>

<template>
  <div class="ds-banner-frame">
    <template v-if="src && !failed">
      <div class="ds-banner-bg" aria-hidden="true" />
      <img :src="src" :alt="alt" class="ds-banner-inner ds-banner-fg" @error="failed = true" />
    </template>
    <div v-else class="ds-banner-inner ds-placeholder"><span class="ds-placeholder-glyph">✺</span></div>
  </div>
</template>
