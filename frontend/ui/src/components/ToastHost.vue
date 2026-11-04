<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppIcon from './AppIcon.vue'
import { useToast, type ToastTone } from './useToast'

// Design v4 Toast / Snackbar (screens/H.jsx Toast, screens/ext2.css .bt2): surface with a hairline strong border and the overlay shadow, icon + title
// + message + optional action + dismiss. success: check; error (danger): alert, danger border, persistent, role=alert; undo: ink snackbar with the
// action and a 6 s brass countdown line. Top-right on desktop; full width above the tab bar on mobile. Hover or focus pauses the timer.
const { t } = useI18n()
const { toasts, dismiss, pause, resume } = useToast()
const IC: Record<ToastTone, string> = { info: 'info', success: 'check', warning: 'alert', danger: 'alert' }
</script>

<template>
  <div class="bt2-host" aria-live="polite">
    <div
      v-for="toast in toasts" :key="toast.id" class="bt2"
      :class="[toast.countdown ? 'bt2--snack' : `bt2--${toast.tone === 'danger' ? 'error' : toast.tone}`]"
      :role="toast.tone === 'danger' ? 'alert' : 'status'"
      @mouseenter="pause(toast.id)" @mouseleave="resume(toast.id)" @focusin="pause(toast.id)" @focusout="resume(toast.id)"
    >
      <AppIcon :name="IC[toast.tone]" :size="16" />
      <div style="flex: 1; min-width: 0"><b>{{ toast.title }}</b><span v-if="toast.body">{{ toast.body }}</span></div>
      <div class="x">
        <button v-if="toast.action" type="button" class="rs-btn rs-btn--sm" @click="toast.action.run(); dismiss(toast.id)">{{ toast.action.label }}</button>
        <button type="button" class="rs-btn rs-btn--ghost rs-btn--icon rs-btn--sm" style="color: inherit" :aria-label="t('common.close')" @click="dismiss(toast.id)"><AppIcon name="x" :size="16" /></button>
      </div>
      <i v-if="toast.countdown" class="tm" />
    </div>
  </div>
</template>
