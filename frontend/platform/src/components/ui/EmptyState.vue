<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Mirrors design/components/core/EmptyState.jsx
withDefaults(defineProps<{ icon?: string; title: string }>(), { icon: 'sparkle' })
</script>

<template>
  <div class="rs-empty">
    <div class="rs-empty__art"><AppIcon :name="icon" :size="28" /></div>
    <h3>{{ title }}</h3>
    <p v-if="$slots.default"><slot /></p>
    <slot name="action" />
  </div>
</template>
