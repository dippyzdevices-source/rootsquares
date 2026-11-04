<script setup lang="ts">
// Mirrors design/components/navigation/Tabs.jsx (roving tabindex, arrow keys). Panel content goes in the default slot.
export interface TabItem { id: string; label: string; count?: number | string; mark?: string; disabled?: boolean }
const props = defineProps<{ tabs: TabItem[]; modelValue: string; label?: string }>()
const emit = defineEmits<{ 'update:modelValue': [id: string] }>()

function key(e: KeyboardEvent, i: number) {
  const en = props.tabs.filter((t) => !t.disabled)
  const idx = en.findIndex((t) => t.id === props.tabs[i]!.id)
  let n: TabItem | undefined
  if (e.key === 'ArrowRight') n = en[(idx + 1) % en.length]
  if (e.key === 'ArrowLeft') n = en[(idx - 1 + en.length) % en.length]
  if (e.key === 'Home') n = en[0]
  if (e.key === 'End') n = en[en.length - 1]
  if (n) {
    e.preventDefault()
    emit('update:modelValue', n.id)
    ;(e.currentTarget as HTMLElement).parentElement?.querySelector<HTMLElement>(`[data-id="${n.id}"]`)?.focus()
  }
}
</script>

<template>
  <div>
    <div class="rs-tabs" role="tablist" :aria-label="label">
      <button
        v-for="(t, i) in tabs" :key="t.id" type="button" role="tab" class="rs-tab"
        :data-id="t.id" :id="`tab-${t.id}`" :aria-selected="modelValue === t.id" :aria-controls="`panel-${t.id}`"
        :tabindex="modelValue === t.id ? 0 : -1" :disabled="t.disabled"
        @click="emit('update:modelValue', t.id)" @keydown="key($event, i)"
      >{{ t.label }}<span v-if="t.mark" class="rs-tab-mark">{{ t.mark }}</span><span v-if="t.count != null" class="rs-badge rs-badge--neutral">{{ t.count }}</span></button>
    </div>
    <div v-if="$slots.default" role="tabpanel" :id="`panel-${modelValue}`" :aria-labelledby="`tab-${modelValue}`" style="padding-top: 16px"><slot /></div>
  </div>
</template>

<style scoped>
/* A small brass tag on a tab, for example 'your package' (W15-R31) */
.rs-tab-mark { padding: 2px 8px; border-radius: var(--shape-control); background: var(--color-brass-subtle); color: var(--color-brass-text); font-size: var(--text-xs); font-weight: 600; letter-spacing: .02em; line-height: 1.4 }
</style>
