<script setup lang="ts">
import { useId } from 'vue'

// Design v3 segmented control with a visible caption (`.bt-seg`, used for Preview mode, device width): single choice, aria-pressed buttons,
// pressed = ink fill. The same markup as the inline control on the Themes screen (TemplatesView).
defineProps<{ items: [string, string][]; modelValue: string; label?: string; ariaLabel?: string }>()
const emit = defineEmits<{ 'update:modelValue': [v: string] }>()
const id = useId()
</script>

<template>
  <div class="bt-seg" role="group" :aria-labelledby="label ? id : undefined" :aria-label="label ? undefined : ariaLabel">
    <span v-if="label" :id="id" class="rs-label">{{ label }}</span>
    <div>
      <button v-for="[v, l] in items" :key="v" type="button" :aria-pressed="modelValue === v" @click="emit('update:modelValue', v)">{{ l }}</button>
    </div>
  </div>
</template>
