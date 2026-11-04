<script setup lang="ts">
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Design v3 toggle group (`.bx-tg`): aria-pressed buttons, selected = brass border + brass-subtle. Multi select by default;
// `single` makes it a single choice (Support access duration, Owner tenant status filter).
export interface ToggleItem { value: string; label: string; icon?: string; count?: number }
const props = defineProps<{ items: ToggleItem[]; modelValue: string[]; label: string; single?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [v: string[]] }>()
const toggle = (v: string) => {
  if (props.single) emit('update:modelValue', [v])
  else emit('update:modelValue', props.modelValue.includes(v) ? props.modelValue.filter((x) => x !== v) : [...props.modelValue, v])
}
</script>

<template>
  <div class="bx-tg" role="group" :aria-label="label">
    <button v-for="it in items" :key="it.value" type="button" :aria-pressed="modelValue.includes(it.value)" @click="toggle(it.value)">
      <AppIcon v-if="it.icon" :name="it.icon" :size="14" />{{ it.label }}<span v-if="it.count !== undefined" class="bs-mute" style="color: var(--color-text-muted)"> {{ it.count }}</span>
    </button>
  </div>
</template>
