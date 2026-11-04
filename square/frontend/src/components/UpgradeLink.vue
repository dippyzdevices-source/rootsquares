<script setup lang="ts">
import { computed } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import { squareProfile } from '../services/squareConfig'

// The way up from a locked feature (W26-R17): most people who read the note are committee members who cannot change the plan, so it says to ask the owner; the
// button to the platform (rootsquares, where the owner changes the package) shows only when the server knows its address (PLATFORM_SITE_URL), and the platform asks to sign in.
const props = withDefaults(defineProps<{ text?: string; button?: string }>(), { text: 'Ask the owner of this square to upgrade the plan on rootsquares.', button: 'Owner: see the packages' })
const href = computed(() => (squareProfile.platformUrl ? `${squareProfile.platformUrl}/dashboard` : ''))
</script>

<template>
  <div class="upgrade-link" data-testid="upgrade-link">
    <p class="ds-caption">{{ props.text }}</p>
    <BaseButton v-if="href" :href="href" variant="secondary" size="sm" target="_blank" rel="noopener">{{ props.button }}</BaseButton>
  </div>
</template>
