<script setup lang="ts">
withDefaults(defineProps<{ width?: string; height?: string; rounded?: string }>(), {
  width: '100%',
  height: '1rem',
  rounded: 'rounded-md',
})
</script>

<template>
  <div class="animate-pulse bg-black/10 dark:bg-white/10" :class="rounded" :style="{ width, height }" />
</template>
