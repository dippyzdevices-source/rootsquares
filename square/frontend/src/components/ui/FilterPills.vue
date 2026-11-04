<script setup lang="ts">
// The status pills of an admin toolbar (All · Live · Draft …). Single choice; sits before the search
// field in a `.ds-toolbar` row. One component so every list page looks and behaves the same.
defineProps<{ modelValue: string; options: { value: string; label: string }[]; label: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="ds-toolbar-pills" role="group" :aria-label="label">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      class="ds-tag"
      :class="{ 'ds-tag-selected': modelValue === option.value }"
      :aria-pressed="modelValue === option.value"
      @click="$emit('update:modelValue', option.value)"
    >
      {{ option.label }}
    </button>
  </div>
</template>
