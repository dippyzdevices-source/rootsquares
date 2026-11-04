<script setup lang="ts">
// Design v3 switch (`.bx-sw`, role="switch", 44px on touch via ext-app.css). The visible label sits next to it in the page; `label` is its accessible name.
defineProps<{ modelValue: boolean; label: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [v: boolean] }>()
</script>

<template>
  <button type="button" class="bx-sw" role="switch" :aria-checked="modelValue" :aria-label="label" :disabled="disabled" @click="emit('update:modelValue', !modelValue)" />
</template>
