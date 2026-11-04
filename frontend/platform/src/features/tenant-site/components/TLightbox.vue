<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

// Gallery lightbox (design "Gallery + lightbox": focus trap, Esc, arrow keys). Teleported to <body> so it covers the viewport, which means it
// sits outside the tenant scope: fixed neutral colours instead of theme variables (MISSING.md).
const props = defineProps<{ labels: string[]; index: number }>()
const emit = defineEmits<{ close: []; 'update:index': [i: number] }>()
const { t } = useI18n()
const box = ref<HTMLElement | null>(null)
let opener: Element | null = null
const step = (d: number) => emit('update:index', (props.index + d + props.labels.length) % props.labels.length)

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
  else if (e.key === 'ArrowLeft') step(-1)
  else if (e.key === 'ArrowRight') step(1)
  else if (e.key === 'Tab' && box.value) {
    const f = [...box.value.querySelectorAll<HTMLElement>('button')]
    const first = f[0]!, last = f[f.length - 1]!
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }
}
onMounted(async () => {
  opener = document.activeElement
  document.addEventListener('keydown', onKey)
  await nextTick()
  box.value?.querySelector<HTMLElement>('[data-close]')?.focus()
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey)
  ;(opener as HTMLElement | null)?.focus?.()
})
</script>

<template>
  <Teleport to="body">
    <div ref="box" class="t-lb" role="dialog" aria-modal="true" :aria-label="labels[index]" @mousedown="(e) => e.target === e.currentTarget && emit('close')">
      <div class="t-lb__ph"><span>{{ labels[index] }}</span></div>
      <div class="t-lb__bar">
        <button type="button" :aria-label="t('site.lightbox.prev')" @click="step(-1)">←</button>
        <button type="button" data-close class="t-lb__close" @click="emit('close')">{{ t('site.lightbox.close') }}</button>
        <button type="button" :aria-label="t('site.lightbox.next')" @click="step(1)">→</button>
      </div>
    </div>
  </Teleport>
</template>
