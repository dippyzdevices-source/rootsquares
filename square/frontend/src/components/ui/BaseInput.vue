<script setup lang="ts">
defineProps<{
  modelValue: string
  label: string
  type?: string
  placeholder?: string
  disabled?: boolean
}>()

defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <label class="block">
    <span class="ds-field-label">{{ label }}</span>
    <input
      :type="type ?? 'text'"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-secondary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:cursor-not-allowed disabled:opacity-60"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </label>
</template>
