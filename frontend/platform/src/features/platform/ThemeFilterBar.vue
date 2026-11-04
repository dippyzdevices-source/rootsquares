<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { SHELL_FILTERS } from './themeFilter'

// Search box, shell chips and the count above a list of themes (W9-R10).
const { t } = useI18n()
defineProps<{ shown: number; counts: Record<string, number> }>()
const q = defineModel<string>('q', { required: true })
const shell = defineModel<string>('shell', { required: true })
</script>

<template>
  <div class="tf-bar">
    <input v-model="q" class="tf-search" type="search" :placeholder="t('themes.search')" :aria-label="t('themes.search')" />
    <div class="tf-chips" role="group" :aria-label="t('themes.shell')">
      <button v-for="f in SHELL_FILTERS" :key="f.id" type="button" class="tf-chip" :aria-pressed="shell === f.id" @click="shell = f.id">{{ f.label }}<small>{{ counts[f.id] }}</small></button>
    </div>
    <span class="tf-count" role="status">{{ t('themes.count', { n: shown }, shown) }}</span>
  </div>
</template>

<style scoped>
.tf-bar { display: grid; gap: 8px; }
.tf-search { height: 44px; padding: 0 14px; border: 1px solid var(--color-border-strong); border-radius: var(--shape-field); background: var(--color-surface); color: var(--color-text); font: inherit; font-size: var(--text-sm); }
.tf-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.tf-chip { min-height: 44px; padding: 0 12px; border: 1px solid var(--color-border); border-radius: var(--shape-control); background: var(--color-surface); color: var(--color-text); font: inherit; font-size: var(--text-xs); cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.tf-chip small { color: var(--color-text-muted); }
.tf-chip[aria-pressed='true'] { border-color: var(--color-brass); background: var(--color-brass-subtle); }
.tf-count { font-size: var(--text-xs); color: var(--color-text-muted); }
</style>
