<script setup lang="ts">
// The design system's Radio (components/forms/Radio.jsx): a 20px ring with a dot, the label beside it
// and an optional muted description. Use several with the same `name` and a shared v-model.
defineProps<{
  modelValue: string
  value: string
  name: string
  label: string
  description?: string
  disabled?: boolean
}>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <label class="base-radio" :class="{ 'base-radio-disabled': disabled }">
    <input
      type="radio"
      class="base-radio-input"
      :name="name"
      :value="value"
      :checked="modelValue === value"
      :disabled="disabled"
      @change="$emit('update:modelValue', value)"
    />
    <span class="base-radio-ring" aria-hidden="true"><span class="base-radio-dot" /></span>
    <span>
      <span class="base-radio-label">{{ label }}</span>
      <span v-if="description" class="base-radio-desc">{{ description }}</span>
    </span>
  </label>
</template>

<style scoped>
.base-radio { display: flex; gap: var(--ds-space-3); align-items: flex-start; cursor: pointer; position: relative; }
.base-radio-disabled { cursor: not-allowed; opacity: 0.5; }
.base-radio-input { position: absolute; opacity: 0; width: 0; height: 0; }
.base-radio-ring { width: 20px; height: 20px; flex: 0 0 20px; margin-top: 2px; border-radius: var(--ds-radius-pill); display: flex; align-items: center; justify-content: center; background: var(--ds-surface-card); border: 1px solid var(--ds-border-strong); transition: border-color 140ms var(--ds-ease); }
.base-radio-dot { width: 10px; height: 10px; border-radius: var(--ds-radius-pill); background: transparent; transition: background-color 140ms var(--ds-ease); }
.base-radio-input:checked + .base-radio-ring { border-color: var(--ds-action-primary); }
.base-radio-input:checked + .base-radio-ring .base-radio-dot { background: var(--ds-action-primary); }
.base-radio-input:focus-visible + .base-radio-ring { outline: 2px solid var(--ds-action-primary); outline-offset: 2px; }
.base-radio-label { display: block; color: var(--ds-text-heading); }
.base-radio-desc { display: block; font-size: var(--ds-text-body-s); color: var(--ds-text-muted); }
</style>
