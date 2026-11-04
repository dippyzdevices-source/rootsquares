<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'

// The design system's themed Select: a custom listbox, not a native <select> (the OS menu paints
// system blue and ignores both themes). v-model works like the native control; `change` fires
// after `update:modelValue`, so handlers written for `@change` keep working.
type Value = string | number
interface Option {
  value: Value
  label: string
  count?: number | null
  divider?: boolean
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue: Value
    options: (Option | string)[]
    label?: string
    hint?: string
    placeholder?: string
    size?: 'sm' | 'md'
    // Tint the control when anything other than the first ("All …") option is chosen.
    highlightActive?: boolean
    disabled?: boolean
    id?: string
    ariaLabel?: string
  }>(),
  { label: undefined, hint: undefined, placeholder: 'Select', size: 'md', highlightActive: false, disabled: false, id: undefined, ariaLabel: undefined },
)

const emit = defineEmits<{ 'update:modelValue': [value: Value]; change: [value: Value] }>()

const uid = props.id ?? `sel-${useId()}`
const root = ref<HTMLElement | null>(null)
const button = ref<HTMLButtonElement | null>(null)
const open = ref(false)
const cursor = ref(-1)

const opts = computed<Option[]>(() =>
  props.options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o)),
)
const selectedIndex = computed(() => opts.value.findIndex((o) => o.value === props.modelValue))
const current = computed(() => opts.value[selectedIndex.value])
const active = computed(() => props.highlightActive && selectedIndex.value > 0)

function openMenu() {
  if (props.disabled) return
  cursor.value = selectedIndex.value < 0 ? 0 : selectedIndex.value
  open.value = true
}
function choose(i: number) {
  const o = opts.value[i]
  if (!o || o.disabled) return
  open.value = false
  button.value?.focus()
  if (o.value !== props.modelValue) {
    emit('update:modelValue', o.value)
    emit('change', o.value)
  }
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
    choose(cursor.value)
  } else if (e.key === 'Tab') {
    open.value = false
  } else if (e.key.length === 1) {
    const k = e.key.toLowerCase()
    const startsWith = (o: Option) => o.label.toLowerCase().startsWith(k)
    const next = opts.value.findIndex((o, i) => i > cursor.value && startsWith(o))
    const found = next >= 0 ? next : opts.value.findIndex(startsWith)
    if (found >= 0) cursor.value = found
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
  <div ref="root" class="base-select" :class="[`base-select-${size}`, { 'base-select-open': open, 'base-select-active': active }]">
    <label v-if="label" :for="uid" class="ds-field-label">{{ label }}</label>
    <button
      :id="uid"
      ref="button"
      type="button"
      class="base-select-button"
      :disabled="disabled"
      :aria-label="ariaLabel"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="open ? (open = false) : openMenu()"
      @keydown="onKey"
    >
      <span class="base-select-value" :class="{ 'base-select-placeholder': !current }">{{ current ? current.label : placeholder }}</span>
      <svg class="base-select-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
    </button>

    <div v-if="open" class="base-select-menu" role="listbox" :aria-labelledby="uid" @click.prevent>
      <div
        v-for="(o, i) in opts"
        :key="String(o.value)"
        role="option"
        :data-value="String(o.value)"
        class="base-select-option"
        :class="{ 'is-selected': i === selectedIndex, 'is-cursor': i === cursor, 'has-divider': o.divider && i > 0, 'is-disabled': o.disabled }"
        :aria-selected="i === selectedIndex"
        @mouseenter="cursor = i"
        @mousedown.prevent
        @click="choose(i)"
      >
        <span class="base-select-option-label">{{ o.label }}</span>
        <span v-if="o.count != null" class="base-select-option-count">{{ o.count }}</span>
        <span class="base-select-option-check">
          <svg v-if="i === selectedIndex" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5" /></svg>
        </span>
      </div>
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
.base-select-placeholder { color: var(--ds-text-faint); }
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
.base-select-option.has-divider { border-top: 1px solid var(--ds-border-hairline); border-radius: 0 0 var(--ds-radius-sm) var(--ds-radius-sm); }
.base-select-option.is-disabled { opacity: 0.45; cursor: not-allowed; }
.base-select-option-label { flex: 1; }
.base-select-option-count { font-size: 12px; color: var(--ds-text-faint); }
.base-select-option-check { width: 16px; display: flex; color: var(--ds-text-primary); }
</style>
