<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'

// BaseSelect's sibling for filters that take several values: the same pill button and menu, but
// every option is a checkbox and the menu stays open while you tick. Nothing ticked means "no
// filter" (the button reads `allLabel`). v-model is the array of ticked values; `change` fires
// after `update:modelValue`. Keeps the `base-select-*` class names, so the page tests'
// `.base-select-button` lookups count both controls the same way.
type Value = string | number
interface Option {
  value: Value
  label: string
  count?: number | null
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue: Value[]
    options: (Option | string)[]
    // Shown on the button when nothing is ticked, e.g. "All ticket types".
    allLabel?: string
    label?: string
    hint?: string
    size?: 'sm' | 'md'
    // Tint the control as soon as anything is ticked.
    highlightActive?: boolean
    disabled?: boolean
    id?: string
    ariaLabel?: string
  }>(),
  { allLabel: 'All', label: undefined, hint: undefined, size: 'md', highlightActive: false, disabled: false, id: undefined, ariaLabel: undefined },
)

const emit = defineEmits<{ 'update:modelValue': [value: Value[]]; change: [value: Value[]] }>()

const uid = props.id ?? `msel-${useId()}`
const root = ref<HTMLElement | null>(null)

const open = ref(false)
const cursor = ref(0)

const opts = computed<Option[]>(() =>
  props.options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o)),
)
const ticked = computed(() => new Set(props.modelValue.map(String)))
const summary = computed(() => {
  const chosen = opts.value.filter((o) => ticked.value.has(String(o.value)))
  if (chosen.length === 0) return props.allLabel
  if (chosen.length === 1) return chosen[0].label
  return `${chosen.length} selected`
})
const active = computed(() => props.highlightActive && props.modelValue.length > 0)

function openMenu() {
  if (props.disabled) return
  cursor.value = 0
  open.value = true
}
function set(next: Value[]) {
  emit('update:modelValue', next)
  emit('change', next)
}
function toggle(i: number) {
  const o = opts.value[i]
  if (!o || o.disabled) return
  const key = String(o.value)
  set(ticked.value.has(key) ? props.modelValue.filter((v) => String(v) !== key) : [...props.modelValue, o.value])
}
function clear() {
  if (props.modelValue.length) set([])
}
function onKey(e: KeyboardEvent) {
  if (props.disabled) return
  if (!open.value) {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
      e.preventDefault()
      openMenu()
    }
    return
  }
  const last = opts.value.length - 1
  if (e.key === 'Escape') {
    e.preventDefault()
    open.value = false
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    cursor.value = Math.min(last, cursor.value + 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    cursor.value = Math.max(0, cursor.value - 1)
  } else if (e.key === 'Home') {
    e.preventDefault()
    cursor.value = 0
  } else if (e.key === 'End') {
    e.preventDefault()
    cursor.value = last
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    toggle(cursor.value)
  } else if (e.key === 'Tab') {
    open.value = false
  }
}

function away(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) open.value = false
}
watch(open, (isOpen) => {
  if (isOpen) document.addEventListener('mousedown', away)
  else document.removeEventListener('mousedown', away)
})
onBeforeUnmount(() => document.removeEventListener('mousedown', away))
</script>

<template>
  <div
    ref="root"
    class="base-select base-multiselect"
    :class="[`base-select-${size}`, { 'base-select-open': open, 'base-select-active': active }]"
  >
    <label v-if="label" :for="uid" class="ds-field-label">{{ label }}</label>
    <button
      :id="uid"

      type="button"
      class="base-select-button"
      :disabled="disabled"
      :aria-label="ariaLabel"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="open ? (open = false) : openMenu()"
      @keydown="onKey"
    >
      <span class="base-select-value">{{ summary }}</span>
      <svg class="base-select-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
    </button>

    <div v-if="open" class="base-select-menu" role="listbox" aria-multiselectable="true" :aria-labelledby="uid" @click.prevent>
      <div
        v-for="(o, i) in opts"
        :key="String(o.value)"
        role="option"
        :data-value="String(o.value)"
        class="base-select-option"
        :class="{ 'is-selected': ticked.has(String(o.value)), 'is-cursor': i === cursor, 'is-disabled': o.disabled }"
        :aria-selected="ticked.has(String(o.value))"
        @mouseenter="cursor = i"
        @mousedown.prevent
        @click="toggle(i)"
      >
        <span class="base-multiselect-box" :class="{ 'is-on': ticked.has(String(o.value)) }" aria-hidden="true">
          <svg v-if="ticked.has(String(o.value))" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
        </span>
        <span class="base-select-option-label">{{ o.label }}</span>
        <span v-if="o.count != null" class="base-select-option-count">{{ o.count }}</span>
      </div>
      <button v-if="modelValue.length" type="button" class="base-multiselect-clear" @mousedown.prevent @click="clear">Clear</button>
    </div>
    <span v-if="hint" class="ds-caption base-select-hint">{{ hint }}</span>
  </div>
</template>

<style scoped>
.base-select { position: relative; display: block; min-width: 0; }
.base-select-hint { display: block; margin-top: var(--ds-space-2); color: var(--ds-text-muted); }
.base-select-button {
  width: 100%; height: 48px; display: flex; align-items: center; gap: var(--ds-space-2); padding: 0 16px 0 18px;
  text-align: left; cursor: pointer; font: 400 var(--ds-text-body-m) / 1.2 var(--ds-font-body);
  color: var(--ds-text-heading); background: var(--ds-surface-card);
  border: 1px solid var(--ds-border-default); border-radius: var(--ds-radius-pill);
  box-shadow: var(--ds-shadow-xs); outline: none;
  transition: background-color 140ms var(--ds-ease), border-color 140ms var(--ds-ease), box-shadow 140ms var(--ds-ease);
}
.base-select-sm .base-select-button { height: 36px; font-size: 14px; }
.base-select-button:hover:not(:disabled) { border-color: var(--ds-border-strong); }
.base-select-button:focus-visible, .base-select-open .base-select-button { border-color: var(--ds-border-primary); box-shadow: 0 0 0 3px var(--ds-focus-ring-soft); }
.base-select-active .base-select-button { background: var(--ds-surface-primary-soft); border-color: var(--ds-border-primary); }
.base-select-button:disabled { background: var(--ds-surface-sunken); cursor: not-allowed; opacity: 0.6; }
.base-select-value { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.base-select-chevron { flex: 0 0 auto; color: var(--ds-text-muted); transition: transform 140ms var(--ds-ease); }
.base-select-active .base-select-chevron { color: var(--ds-text-primary); }
.base-select-open .base-select-chevron { transform: rotate(180deg); }
.base-select-menu {
  position: absolute; top: calc(100% + 6px); left: 0; min-width: 100%; z-index: 40; max-height: 320px; overflow-y: auto;
  padding: var(--ds-space-2); background: var(--ds-surface-card); border: 1px solid var(--ds-border-hairline);
  border-radius: var(--ds-radius-md); box-shadow: var(--ds-shadow-lg);
}
.base-select-option {
  display: flex; align-items: center; gap: var(--ds-space-3); padding: 9px 10px; border-radius: var(--ds-radius-sm);
  cursor: pointer; white-space: nowrap; font: 400 15px / 1.3 var(--ds-font-body); color: var(--ds-text-body);
}
.base-select-option.is-cursor { background: var(--ds-action-ghost-hover); }
.base-select-option.is-selected { color: var(--ds-text-primary); font-weight: 600; }
.base-select-option.is-disabled { opacity: 0.45; cursor: not-allowed; }
.base-select-option-label { flex: 1; }
.base-select-option-count { font-size: 12px; color: var(--ds-text-faint); }
.base-multiselect-box {
  width: 18px; height: 18px; flex: 0 0 18px; display: flex; align-items: center; justify-content: center;
  border-radius: var(--ds-radius-xs); border: 1px solid var(--ds-border-strong); background: var(--ds-surface-card);
  color: var(--ds-text-on-primary);
}
.base-multiselect-box.is-on { background: var(--ds-action-primary); border-color: var(--ds-action-primary); }
.base-multiselect-clear {
  display: block; width: 100%; margin-top: var(--ds-space-2); padding: 9px 10px; border: 0; border-top: 1px solid var(--ds-border-hairline);
  background: transparent; text-align: left; cursor: pointer; font: 500 14px / 1.3 var(--ds-font-body); color: var(--ds-text-primary);
}
.base-multiselect-clear:hover { text-decoration: underline; }
</style>
