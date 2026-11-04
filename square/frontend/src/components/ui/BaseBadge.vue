<script setup lang="ts">
withDefaults(defineProps<{ variant?: 'default' | 'success' | 'error' }>(), {
  variant: 'default',
})
</script>

<template>
  <span
    class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
    :class="{
      'bg-black/5 dark:bg-white/10 text-text-secondary': variant === 'default',
      'bg-success-bg text-success': variant === 'success',
      'bg-error-bg text-error': variant === 'error',
    }"
  >
    <slot />
  </span>
</template>
