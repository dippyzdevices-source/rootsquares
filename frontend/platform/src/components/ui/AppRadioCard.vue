<script setup lang="ts">
// Radio option row (.bs-opt): radio + title + hint; selected = brass border + brass-subtle fill.
// design/rootsquares-platform-brass/export/components.md ("Option row") and screens/A.jsx Wizard.
const props = defineProps<{ modelValue: string; value: string; title: string; hint?: string }>()
const emit = defineEmits<{ 'update:modelValue': [v: string] }>()
const select = () => emit('update:modelValue', props.value)
</script>

<template>
  <div class="bs-opt" role="radio" tabindex="0" :aria-checked="modelValue === value" style="cursor: pointer" @click="select" @keydown.enter.prevent="select" @keydown.space.prevent="select">
    <span class="bs-radio" />
    <div><b>{{ title }}</b><small v-if="hint">{{ hint }}</small></div>
  </div>
</template>
