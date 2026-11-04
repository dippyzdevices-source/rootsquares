<script setup lang="ts">
withDefaults(defineProps<{ variant?: 'info' | 'success' | 'error' }>(), {
  variant: 'info',
})
</script>

<template>
  <div
    role="alert"
    class="rounded-md border px-4 py-3 text-sm"
    :class="{
      'border-border bg-surface text-text': variant === 'info',
      'border-success/20 bg-success-bg text-success': variant === 'success',
      'border-error/20 bg-error-bg text-error': variant === 'error',
    }"
  >
    <slot />
  </div>
</template>
