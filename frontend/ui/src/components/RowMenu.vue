<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from './AppIcon.vue'

// Design v3 row actions menu (`.bx-menu`, `.bx-pop`, D.jsx Menu): ghost icon button + popover; danger item last after a divider.
// Keyboard: Enter/Space/ArrowDown opens and focuses the first item, ArrowUp/Down move, Home/End, Escape closes and returns focus.
export interface MenuItem { id: string; label: string; icon: string; danger?: boolean }
const props = defineProps<{ items: (MenuItem | '-')[]; label?: string }>()
const emit = defineEmits<{ select: [id: string] }>()

const { t } = useI18n()
const open = ref(false)
const root = ref<HTMLElement | null>(null)
const btn = ref<HTMLButtonElement | null>(null)
const menuId = useId()

const itemEls = () => [...(root.value?.querySelectorAll<HTMLElement>('[role=menuitem]') ?? [])]
async function show() {
  open.value = true
  document.addEventListener('mousedown', outside)
  await nextTick()
  itemEls()[0]?.focus()
}
function hide(refocus = true) {
  open.value = false
  document.removeEventListener('mousedown', outside)
  if (refocus) btn.value?.focus()
}
const outside = (e: MouseEvent) => { if (root.value && !root.value.contains(e.target as Node)) hide(false) }
function onBtnKey(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') { e.preventDefault(); void show() }
}
function onMenuKey(e: KeyboardEvent) {
  const els = itemEls()
  const i = els.indexOf(document.activeElement as HTMLElement)
  if (e.key === 'Escape') { e.preventDefault(); hide() }
  else if (e.key === 'ArrowDown') { e.preventDefault(); els[(i + 1) % els.length]?.focus() }
  else if (e.key === 'ArrowUp') { e.preventDefault(); els[(i - 1 + els.length) % els.length]?.focus() }
  else if (e.key === 'Home') { e.preventDefault(); els[0]?.focus() }
  else if (e.key === 'End') { e.preventDefault(); els[els.length - 1]?.focus() }
  else if (e.key === 'Tab') hide(false)
}
function pick(id: string) { hide(); emit('select', id) }
onBeforeUnmount(() => document.removeEventListener('mousedown', outside))
void props
</script>

<template>
  <div ref="root" class="bx-menu">
    <button ref="btn" type="button" class="rs-btn rs-btn--ghost rs-btn--icon" aria-haspopup="menu" :aria-expanded="open" :aria-controls="open ? menuId : undefined" :aria-label="label ?? t('bx.rowActions')" @click="open ? hide() : show()" @keydown="onBtnKey">
      <AppIcon name="more" :size="16" />
    </button>
    <div v-if="open" :id="menuId" class="bx-pop" role="menu" @keydown="onMenuKey">
      <template v-for="(it, k) in items" :key="typeof it === 'string' ? `sep${k}` : it.id">
        <hr v-if="typeof it === 'string'" role="separator">
        <button v-else type="button" role="menuitem" :class="it.danger && 'dg'" @click="pick(it.id)"><AppIcon :name="it.icon" :size="14" />{{ it.label }}</button>
      </template>
    </div>
  </div>
</template>
