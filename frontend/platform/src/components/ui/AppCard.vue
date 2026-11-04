<script setup lang="ts">
// Mirrors design/components/core/Card.jsx (.rs-card)
withDefaults(defineProps<{ as?: string; title?: string; flat?: boolean; interactive?: boolean }>(), { as: 'div' })
</script>

<template>
  <component :is="as" class="rs-card" :class="[flat && 'rs-card--flat', interactive && 'rs-card--interactive']">
    <h3 v-if="title" class="rs-card__title" style="margin-bottom: 8px">{{ title }}</h3>
    <slot />
  </component>
</template>
