<script setup lang="ts">
import AppIcon from './AppIcon.vue'
import { Teleport, computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'

// Design v3 Confirm dialog (`.bx-dlg`, D.jsx Confirm): role="alertdialog"; with `name` the destructive button stays disabled until the typed
// value equals the name exactly. Without `name` it is a plain dialog (form content in the default slot, `tone="primary"` for a non-destructive
// action). `inline` renders only the box (showcase); otherwise a teleported modal with focus trap, Escape and focus return.
const props = withDefaults(defineProps<{
  title: string
  verb: string
  icon?: string // the icon before the verb; a red button without one gets the warning sign, a primary one the tick
  body?: string
  name?: string
  tone?: 'danger' | 'primary'
  confirmDisabled?: boolean
  inline?: boolean
  wide?: boolean // a form with many fields: up to 760px instead of 440px
  roomy?: boolean // a dialog with several facts to read: 560px wide, more space inside (W23-R61)
}>(), { tone: 'danger', inline: false, wide: false, roomy: false })
const emit = defineEmits<{ confirm: []; cancel: [] }>()

const { t } = useI18n()
const id = useId()
const typed = ref('')
const ok = computed(() => (props.name ? typed.value === props.name : true) && !props.confirmDisabled)
const box = ref<HTMLElement | null>(null)
let opener: Element | null = null

const onKey = (e: KeyboardEvent) => {
  if (e.key === 'Escape') emit('cancel')
  if (e.key === 'Tab' && box.value) {
    const f = [...box.value.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])')]
    if (!f.length) return
    const first = f[0]!, last = f[f.length - 1]!
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }
}
onMounted(async () => {
  if (props.inline) return
  opener = document.activeElement
  document.addEventListener('keydown', onKey)
  await nextTick()
  const first = box.value?.querySelector<HTMLElement>('input,select,textarea') ?? box.value?.querySelector<HTMLElement>('button:not([disabled])')
  first?.focus()
})
onBeforeUnmount(() => {
  if (props.inline) return
  document.removeEventListener('keydown', onKey)
  ;(opener as HTMLElement | null)?.focus?.()
})
</script>

<template>
  <component :is="inline ? 'div' : Teleport" v-bind="inline ? {} : { to: 'body' }">
    <div :class="!inline && 'rs rs-modal-host'" :style="inline ? undefined : 'position: fixed; background: var(--color-overlay)'" @mousedown="(e) => !inline && e.target === e.currentTarget && emit('cancel')">
      <div ref="box" class="bx-dlg" :class="roomy && 'bx-dlg--roomy'" role="alertdialog" aria-modal="true" :aria-labelledby="`${id}-t`" :aria-describedby="body ? `${id}-d` : undefined" :style="inline ? undefined : `width: min(${wide ? 760 : roomy ? 560 : 440}px, 100%); max-width: ${wide ? 760 : roomy ? 560 : 440}px; max-height: calc(100dvh - 32px); overflow: auto`">
        <h3 :id="`${id}-t`" style="font-family: var(--font-heading); font-weight: 600; letter-spacing: -0.015em">{{ title }}</h3>
        <p v-if="body" :id="`${id}-d`">{{ body }}</p>
        <slot />
        <div v-if="name" class="rs-field" style="gap: 6px">
          <label class="rs-label" :for="`${id}-i`">{{ t('bx.typeBefore') }} <code>{{ name }}</code> {{ t('bx.typeAfter') }}</label>
          <input :id="`${id}-i`" v-model="typed" class="rs-input" autocomplete="off" :aria-invalid="typed.length >= name.length && !ok ? true : undefined">
        </div>
        <footer>
          <button type="button" class="rs-btn rs-btn--secondary" @click="emit('cancel')"><AppIcon name="x" />{{ t('common.cancel') }}</button>
          <button type="button" class="rs-btn" :class="tone === 'danger' && 'bx-btn-danger'" :disabled="!ok" @click="emit('confirm')"><AppIcon :name="icon ?? (tone === 'danger' ? 'alert' : 'check')" />{{ verb }}</button>
        </footer>
      </div>
    </div>
  </component>
</template>
