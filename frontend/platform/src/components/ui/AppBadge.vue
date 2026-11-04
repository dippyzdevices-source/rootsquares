<script setup lang="ts">
// Mirrors design/components/core/Badge.jsx (.rs-badge: count badge)
withDefaults(defineProps<{ tone?: 'accent' | 'neutral' | 'danger' }>(), { tone: 'accent' })
</script>

<template>
  <span class="rs-badge" :class="tone !== 'accent' && `rs-badge--${tone}`"><slot /></span>
</template>
