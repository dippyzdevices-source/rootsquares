<script setup lang="ts">
// Mirrors design/components/extras/SegmentedControl.jsx (.rs-seg)
defineProps<{ items: [string, string][]; modelValue: string; label?: string; labelledby?: string }>()
const emit = defineEmits<{ 'update:modelValue': [v: string] }>()
</script>

<template>
  <div class="rs-seg" role="group" :aria-label="label" :aria-labelledby="labelledby">
    <button v-for="[v, l] in items" :key="v" type="button" :aria-pressed="modelValue === v" @click="emit('update:modelValue', v)">{{ l }}</button>
  </div>
</template>
