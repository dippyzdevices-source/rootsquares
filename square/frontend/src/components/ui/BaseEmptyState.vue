<script setup lang="ts">
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <div class="flex flex-col items-center gap-2 px-6 py-12 text-center">
    <h3 class="text-base font-semibold text-text">{{ title }}</h3>
    <p v-if="description" class="text-sm text-text-secondary">{{ description }}</p>
    <div v-if="$slots.action" class="mt-2">
      <slot name="action" />
    </div>
  </div>
</template>
