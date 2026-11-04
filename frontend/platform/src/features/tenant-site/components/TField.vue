<script setup lang="ts">
import { useId } from 'vue'

const props = withDefaults(defineProps<{ label: string; modelValue: string; as?: 'input' | 'textarea' | 'select'; type?: string; options?: { value: string; label: string }[]; error?: string; autocomplete?: string }>(), { as: 'input', type: 'text' })
const emit = defineEmits<{ 'update:modelValue': [v: string]; blur: [] }>()
const id = useId()
const on = (e: Event) => emit('update:modelValue', (e.target as HTMLInputElement).value)
void props
</script>

<template>
  <div class="t-field">
    <label :for="id">{{ label }}</label>
    <select v-if="as === 'select'" :id="id" class="t-input" :value="modelValue" @change="on">
      <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
    <textarea v-else-if="as === 'textarea'" :id="id" class="t-input" rows="5" :value="modelValue" :aria-invalid="!!error" :aria-describedby="error ? `${id}-e` : undefined" @input="on" @blur="emit('blur')" />
    <input v-else :id="id" class="t-input" :type="type" :value="modelValue" :autocomplete="autocomplete" :aria-invalid="!!error" :aria-describedby="error ? `${id}-e` : undefined" @input="on" @blur="emit('blur')">
    <span v-if="error" :id="`${id}-e`" class="t-error"><span aria-hidden="true">× </span>{{ error }}</span>
  </div>
</template>
