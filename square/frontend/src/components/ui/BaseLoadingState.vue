<script setup lang="ts">
import BaseSpinner from './BaseSpinner.vue'
import { randomSpinnerVariant } from '../../utils/spinner'

withDefaults(defineProps<{ label?: string }>(), { label: 'Loading…' })

// One of the 5 design-system motif spinners, picked once per mount (not per render) so it
// doesn't flicker between variants while the same loading state is still showing.
const variant = randomSpinnerVariant()
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
    <BaseSpinner :variant="variant" size="xl" />
    <p class="text-sm text-text-secondary">{{ label }}</p>
  </div>
</template>
