<script setup lang="ts">
import BaseSelect from './BaseSelect.vue'
// The per-item override of the site-wide description typeface ("" = site default). Used by the
// news, gallery-album and magazine admin forms (events carry their own inline copy).
defineProps<{ what: string; error?: string }>()
const model = defineModel<string>({ default: '' })
</script>

<template>
  <label class="ds-field">
    <span class="ds-field-label">Description style</span>
    <BaseSelect v-model="model" :options="[{ value: '', label: 'Site default' }, { value: 'karla', label: 'Karla' }, { value: 'cormorant', label: 'Cormorant Garamond' }, { value: 'source', label: 'Source Serif 4' }]" aria-label="Description style" />
    <span class="ds-field-hint">Overrides the site-wide description style for this {{ what }} only. Leave on "Site default" unless it needs its own look.</span>
    <span v-if="error" class="ds-field-error-text">{{ error }}</span>
  </label>
</template>
