<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Design v3 icon button (`.bx-ib`): 30px (44px on touch), hover accent-subtle, optional pressed state. `label` is required (accessible name).
defineProps<{ icon: string; label: string; pressed?: boolean; disabled?: boolean; size?: number }>()
</script>

<template>
  <button type="button" class="bx-ib" :aria-label="label" :title="label" :aria-pressed="pressed" :disabled="disabled"><AppIcon :name="icon" :size="size ?? 16" /></button>
</template>
