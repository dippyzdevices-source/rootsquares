<script setup lang="ts">
// A picture in a fixed-ratio box (no layout shift), lazy loaded; without a picture the striped placeholder stays as the empty state (W9-R5).
defineProps<{ src?: string | null; alt?: string; ratio?: string; radius?: string }>()
</script>

<template>
  <div class="lt-photo" :class="{ 'lt-photo-empty': !src }" :style="{ aspectRatio: ratio, borderRadius: radius }">
    <img v-if="src" :src="src" :alt="alt || ''" loading="lazy" />
    <slot />
  </div>
</template>
