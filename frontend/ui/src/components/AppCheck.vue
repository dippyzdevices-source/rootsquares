<script setup lang="ts">
// Mirrors design/components/forms/Checkbox.jsx (checkbox and radio). For a checkbox v-model is a boolean;
// for a radio pass `value` and v-model holds the selected value.
const props = withDefaults(defineProps<{
  type?: 'checkbox' | 'radio'
  label: string
  description?: string
  modelValue?: boolean | string
  value?: string
  name?: string
  disabled?: boolean
}>(), { type: 'checkbox' })
const emit = defineEmits<{ 'update:modelValue': [v: boolean | string] }>()
const checked = () => (props.type === 'radio' ? props.modelValue === props.value : !!props.modelValue)
const onChange = (e: Event) => emit('update:modelValue', props.type === 'radio' ? props.value! : (e.target as HTMLInputElement).checked)
</script>

<template>
  <label class="rs-check">
    <input :type="type" :name="name" :value="value" :checked="checked()" :disabled="disabled" @change="onChange">
    <span>{{ label }}<small v-if="description">{{ description }}</small></span>
  </label>
</template>
