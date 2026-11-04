<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AnalyticsCard from './AnalyticsCard.vue'
import { useSquare } from './squareContext'

// Analytics (ADR 090): its own section of the square's portal since W23-R80 (it was the card at the bottom of Health). The card holds the switch, the numbers and the
// explanations; this page only gives it a place and a heading, like the other pages of a square.
const { t } = useI18n()
const { sq } = useSquare()
</script>

<template>
  <template v-if="sq">
    <div class="bw-hd"><h2 class="bs-h2" style="font-size: 28px">{{ t('portal.nav.analytics') }}</h2><p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('analytics.pageLede') }}</p></div>
    <AnalyticsCard class="an-page" />
  </template>
</template>

<style scoped>
.an-page { margin-top: 0; }
</style>
