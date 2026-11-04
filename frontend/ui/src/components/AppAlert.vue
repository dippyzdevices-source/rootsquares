<script setup lang="ts">
import AppIcon from './AppIcon.vue'

// Design v3 Alert (screens/ext.css `.bx-al`, D.jsx Alert): icon + title + text + optional action; 2px coloured inline-start rule on a subtle fill.
// `banner` = full width, bottom rule only. Danger uses role="alert".
const props = withDefaults(defineProps<{ tone?: 'info' | 'success' | 'warning' | 'danger'; title?: string; banner?: boolean }>(), { tone: 'info' })
const IC = { info: 'info', success: 'check', warning: 'alert', danger: 'alert' } as const
</script>

<template>
  <div class="bx-al" :class="[`bx-al--${tone}`, banner && 'bx-al--banner']" :role="props.tone === 'danger' ? 'alert' : 'status'">
    <AppIcon :name="IC[tone]" :size="16" />
    <div><b v-if="title">{{ title }}</b><span><slot /></span></div>
    <slot name="action" />
  </div>
</template>
