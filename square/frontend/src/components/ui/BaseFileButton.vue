<script setup lang="ts">
// The one file-picker button: a design-system button wrapping a visually hidden native input.
// Emits the native `change` event untouched, so callers keep reading `event.target.files`.
withDefaults(
  defineProps<{
    accept?: string
    multiple?: boolean
    disabled?: boolean
    variant?: 'primary' | 'secondary' | 'ghost'
    size?: 'sm' | 'md' | 'lg'
  }>(),
  { accept: undefined, multiple: false, disabled: false, variant: 'secondary', size: 'md' },
)
defineEmits<{ change: [event: Event] }>()
</script>

<template>
  <label
    class="ds-btn base-file-button"
    :class="[`ds-btn-${variant}`, `ds-btn-${size}`, { 'base-file-button-disabled': disabled }]"
  >
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
    <slot>Choose file</slot>
    <input
      type="file"
      class="base-file-button-input"
      :accept="accept"
      :multiple="multiple"
      :disabled="disabled"
      @change="$emit('change', $event)"
    />
  </label>
</template>

<style scoped>
.base-file-button { position: relative; cursor: pointer; }
.base-file-button-input { position: absolute; width: 1px; height: 1px; overflow: hidden; opacity: 0; }
.base-file-button:focus-within { outline: 2px solid var(--ds-focus-ring); outline-offset: 2px; }
.base-file-button-disabled { opacity: 0.42; cursor: not-allowed; }
</style>
