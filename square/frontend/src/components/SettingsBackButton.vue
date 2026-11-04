<script setup lang="ts">
import BaseButton from './ui/BaseButton.vue'
import { useSettingsBack } from '../composables/useSettingsGroup'

// The small "Back" button at the top right of a Settings sub-page (W8-R4), like the other admin Back buttons. It goes back to the tab's cards;
// nothing on the hub, on Lists, or on a new/edit form (those have their own Back to the list).
const back = useSettingsBack()
</script>

<template>
  <BaseButton v-if="back" type="button" :to="back.to" variant="secondary" size="sm" :aria-label="back.label">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
    Back
  </BaseButton>
</template>
