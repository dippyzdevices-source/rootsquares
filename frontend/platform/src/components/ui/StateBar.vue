<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// Design v3 "View state" control (E.jsx StateBar, `.bt-seg`): switches a screen between default / loading / empty / error (Domain: its own states).
// It is a review aid of the prototype: shown only in development builds (`npm run dev`), never in production builds.
export type ViewState = string
defineProps<{ modelValue: ViewState; options: [string, string][] }>()
const emit = defineEmits<{ 'update:modelValue': [v: ViewState] }>()
const { t } = useI18n()
const show = import.meta.env.DEV
</script>

<template>
  <div v-if="show" class="bt-seg" role="group" :aria-label="t('bx.viewState')" style="flex-wrap: wrap">
    <span class="rs-label" style="color: var(--color-text-muted); font-weight: 400; font-size: var(--text-xs)">{{ t('bx.viewState') }}</span>
    <div><button v-for="[v, l] in options" :key="v" type="button" :aria-pressed="modelValue === v" @click="emit('update:modelValue', v)">{{ l }}</button></div>
  </div>
</template>
