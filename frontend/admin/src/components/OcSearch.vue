<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Search box of the owner console pages (W11-R75): an icon, the field, a brass border while typing. `label` is the accessible name.
defineProps<{ modelValue: string; placeholder: string; label: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <label class="oc-fld oc-fld--s">
    <AppIcon name="search" :size="16" />
    <input type="search" :value="modelValue" :placeholder="placeholder" :aria-label="label" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)">
  </label>
</template>
