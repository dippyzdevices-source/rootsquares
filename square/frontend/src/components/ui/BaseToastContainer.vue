<script setup lang="ts">
import { useToast } from '../../composables/useToast'

const { toasts, dismiss } = useToast()
</script>

<template>
  <Teleport to="body">
    <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        role="status"
        class="w-72 rounded-md border px-4 py-3 text-sm shadow-md"
        :class="{
          'border-border bg-surface text-text': toast.variant === 'info',
          'border-success/20 bg-success-bg text-success': toast.variant === 'success',
          'border-error/20 bg-error-bg text-error': toast.variant === 'error',
        }"
      >
        <div class="flex items-start justify-between gap-3">
          <span>{{ toast.message }}</span>
          <button
            type="button"
            aria-label="Dismiss"
            class="text-current opacity-60 hover:opacity-100"
            @click="dismiss(toast.id)"
          >
            &#10005;
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
