<script setup lang="ts">
import { computed, ref, useAttrs } from 'vue'

// The design system's SearchField: leading magnifier, clear button, Escape clears. Extra attrs
// (aria-label, @keyup.enter, …) land on the real <input>, so existing handlers keep working;
// `class` and `style` stay on the root so layout classes (.ds-toolbar-search) size the whole field.
defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{ modelValue: string; placeholder?: string; size?: 'sm' | 'md'; disabled?: boolean }>(),
  { placeholder: 'Search', size: 'md', disabled: false },
)
const emit = defineEmits<{ 'update:modelValue': [value: string]; clear: [] }>()

const attrs = useAttrs()
const inputAttrs = computed(() => {
  const { class: _class, style: _style, ...rest } = attrs
  return rest
})
const input = ref<HTMLInputElement | null>(null)
const has = computed(() => props.modelValue.length > 0)

function clear() {
  emit('update:modelValue', '')
  emit('clear')
  input.value?.focus()
}
function onEscape(e: KeyboardEvent) {
  if (!has.value) return
  e.preventDefault()
  clear()
}
</script>

<template>
  <span class="base-search" :class="[`base-search-${size}`, { 'base-search-disabled': disabled }, attrs.class]" :style="attrs.style as never" @click="input?.focus()">
    <svg class="base-search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
    <input
      ref="input"
      v-bind="inputAttrs"
      type="search"
      class="base-search-input"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @keydown.esc="onEscape"
    />
    <button v-if="has && !disabled" type="button" class="base-search-clear" aria-label="Clear search" title="Clear search" @click.stop="clear">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg>
    </button>
  </span>
</template>

<style scoped>
.base-search {
  display: flex; align-items: center; gap: var(--ds-space-2); height: 48px; padding: 0 8px 0 18px; cursor: text; min-width: 0;
  background: var(--ds-surface-card); border: 1px solid var(--ds-border-default); border-radius: var(--ds-radius-pill);
  box-shadow: var(--ds-shadow-xs);
  transition: background-color 140ms var(--ds-ease), border-color 140ms var(--ds-ease), box-shadow 140ms var(--ds-ease);
}
.base-search-sm { height: 36px; }
.base-search:hover:not(.base-search-disabled) { border-color: var(--ds-border-strong); }
.base-search:focus-within { border-color: var(--ds-border-primary); box-shadow: 0 0 0 3px var(--ds-focus-ring-soft); }
.base-search-disabled { background: var(--ds-surface-sunken); cursor: not-allowed; }
.base-search-icon { flex: 0 0 auto; color: var(--ds-text-faint); transition: color 140ms var(--ds-ease); }
.base-search:focus-within .base-search-icon { color: var(--ds-text-primary); }
.base-search-input {
  flex: 1; min-width: 0; height: 100%; border: none; outline: none; background: transparent; appearance: none;
  font: 400 var(--ds-text-body-m) / 1.2 var(--ds-font-body); color: var(--ds-text-heading);
}
.base-search-sm .base-search-input { font-size: 14px; }
.base-search-input::-webkit-search-cancel-button { display: none; }
.base-search-clear {
  width: 28px; height: 28px; flex: 0 0 auto; display: flex; align-items: center; justify-content: center; border: 0;
  border-radius: var(--ds-radius-pill); cursor: pointer; color: var(--ds-text-muted);
  background: color-mix(in oklab, var(--ds-text-heading) 7%, transparent);
}
.base-search-clear:hover { background: color-mix(in oklab, var(--ds-text-heading) 13%, transparent); }
</style>
