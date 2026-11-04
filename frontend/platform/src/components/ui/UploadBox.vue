<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@rootsquares/ui/components/AppIcon.vue'

// Design v3 Upload (`.bx-up`, `.bx-file`, `.bx-pt`; D.jsx Upload). kind file | portrait (4:5). States: default, loading (progress), error, preview.
// Preview only: the file never leaves the browser.
withDefaults(defineProps<{
  kind?: 'file' | 'portrait'
  state?: 'default' | 'loading' | 'error' | 'preview'
  name?: string
  meta?: string // preview line, for example "412 KB · uploaded today"
  progress?: number
  errorText?: string // error detail line (already translated)
  accept?: string // file input accept, default image/* for portraits
  prompt?: string // empty-state title override (already translated)
  hint?: string // empty-state hint override (already translated)
}>(), { kind: 'file', state: 'default', progress: 0 })
const emit = defineEmits<{ choose: [files: FileList | null]; cancel: []; remove: []; replace: [] }>()

const { t } = useI18n()
const input = ref<HTMLInputElement | null>(null)
const pick = () => input.value?.click()
</script>

<template>
  <div>
    <input ref="input" type="file" class="rs-sr" tabindex="-1" :accept="accept ?? (kind === 'portrait' ? 'image/*' : undefined)" @change="emit('choose', ($event.target as HTMLInputElement).files)">
    <div v-if="state === 'loading'" class="bx-file">
      <span class="bx-th">…</span>
      <div>
        <div>{{ name }}</div>
        <div class="bx-pbar" role="progressbar" :aria-label="t('bx.uploading')" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100"><i :style="{ width: progress + '%' }" /></div>
      </div>
      <button type="button" class="rs-btn rs-btn--ghost rs-btn--sm" @click="emit('cancel')"><AppIcon name="x" :size="14" />{{ t('common.cancel') }}</button>
    </div>
    <div v-else-if="state === 'error'" class="bx-up bx-up--err" role="alert">
      <AppIcon name="alert" :size="18" />
      <b style="font-weight: 500">{{ t('bx.tooLargeTitle') }}</b>
      <small style="color: var(--color-text)">{{ errorText }}</small>
      <button type="button" class="rs-btn rs-btn--secondary rs-btn--sm" @click="pick"><AppIcon name="upload" :size="14" />{{ t('bx.chooseAnother') }}</button>
    </div>
    <div v-else-if="state === 'preview' && kind === 'portrait'" style="display: flex; gap: 14px; align-items: flex-start">
      <div class="bx-pt">{{ t('bx.portrait') }}</div>
      <div style="display: grid; gap: 8px; font-size: var(--text-sm)">
        <span>{{ name }}<br><small class="bs-mute">{{ meta }}</small></span>
        <div class="bs-row" style="flex-wrap: wrap">
          <button type="button" class="rs-btn rs-btn--secondary rs-btn--sm" @click="emit('replace'); pick()"><AppIcon name="edit" :size="14" />{{ t('bx.replace') }}</button>
          <button type="button" class="rs-btn rs-btn--ghost rs-btn--sm" @click="emit('remove')"><AppIcon name="trash" :size="14" />{{ t('bx.remove') }}</button>
        </div>
      </div>
    </div>
    <div v-else-if="state === 'preview'" class="bx-file">
      <span class="bx-th">{{ (name ?? '').split('.').pop()?.toUpperCase().slice(0, 4) }}</span>
      <div><div>{{ name }}</div><small class="bs-mute">{{ meta }}</small></div>
      <button type="button" class="rs-btn rs-btn--ghost rs-btn--sm" :aria-label="t('bx.removeFile')" @click="emit('remove')"><AppIcon name="trash" :size="14" /></button>
    </div>
    <div v-else class="bx-up">
      <AppIcon name="upload" :size="20" />
      <b style="font-weight: 500">{{ prompt ?? (kind === 'portrait' ? t('bx.addPortrait') : t('bx.dropFile')) }}</b>
      <small>{{ hint ?? (kind === 'portrait' ? t('bx.portraitHint') : t('bx.fileHint')) }}</small>
      <button type="button" class="rs-btn rs-btn--secondary rs-btn--sm" @click="pick"><AppIcon name="upload" :size="14" />{{ t('bx.chooseFile') }}</button>
    </div>
  </div>
</template>
