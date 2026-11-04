<script setup lang="ts">
import { onBeforeUnmount, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Design v3 Copy field (`.bx-cf`, D.jsx CopyField): mono read-only value + secondary Copy button; the label switches to "Copied" for 1.6s.
// States: default, empty (disabled), loading (skeleton), error (fallback hint).
const props = defineProps<{ label: string; value?: string; state?: 'default' | 'empty' | 'loading' | 'error' }>()
const { t } = useI18n()
const id = useId()
const copied = ref(false)
const failed = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

async function copy() {
  failed.value = false
  try {
    await navigator.clipboard.writeText(props.value ?? '')
    copied.value = true
    clearTimeout(timer)
    timer = setTimeout(() => (copied.value = false), 1600)
  } catch {
    failed.value = true
  }
}
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <div class="rs-field" style="gap: 6px">
    <span :id="id" class="rs-label">{{ label }}</span>
    <span v-if="state === 'loading'" class="bx-sk" style="height: 34px" role="status" :aria-label="t('bx.loading')" />
    <div v-else-if="state === 'empty'" class="bx-cf">
      <code style="color: var(--color-text-muted)">{{ t('bx.afterSave') }}</code>
      <button type="button" class="rs-btn rs-btn--secondary" disabled><AppIcon name="copy" :size="14" />{{ t('bx.copy') }}</button>
    </div>
    <div v-else class="bx-cf">
      <code :aria-labelledby="id">{{ value }}</code>
      <button type="button" class="rs-btn rs-btn--secondary" @click="copy">
        <template v-if="copied"><AppIcon name="check" :size="14" />{{ t('bx.copied') }}</template>
        <template v-else><AppIcon name="copy" :size="14" />{{ t('bx.copy') }}</template>
      </button>
    </div>
    <span v-if="state === 'error' || failed" class="bx-err"><AppIcon name="alert" :size="13" />{{ t('bx.copyFailed') }}</span>
    <span class="rs-sr" role="status">{{ copied ? t('bx.copied') : '' }}</span>
  </div>
</template>
