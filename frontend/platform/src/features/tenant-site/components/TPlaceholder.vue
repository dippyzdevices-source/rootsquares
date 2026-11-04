<script setup lang="ts">
// Labelled placeholder: the design supplies no photography.
withDefaults(defineProps<{ ratio?: string; label?: string; shape?: 'img' | 'lg' | 'md' | 'none' }>(), { ratio: '16/9', label: 'photo', shape: 'img' })
</script>

<template>
  <div class="t-ph" :class="`t-ph--${shape}`" :style="{ aspectRatio: ratio }" role="img" :aria-label="label"><span>{{ label }}</span></div>
</template>
