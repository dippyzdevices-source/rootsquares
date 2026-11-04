<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppButton from '@rootsquares/ui/components/AppButton.vue'
import AppField from '@rootsquares/ui/components/AppField.vue'
import ThemePreviewPane from '@/features/platform/ThemePreviewPane.vue'
import { THEMES } from '@rootsquares/ui/themes'
import { useUiStore } from '@rootsquares/ui/stores/ui'

// Interactive launch preview: type a name, see the site in one look. Shows the real demo site in a frame when it is running
// (ThemePreviewPane, neutral sample content), else the sketch; follows the page's light or dark mode. The button opens the Templates page, where all the looks are.
const { t } = useI18n()
const ui = useUiStore()
const name = ref('')

const shown = computed(() => name.value.trim() || t('landing.launch.placeholder'))
const theme = THEMES[0]! // one look is shown here (the original); the others are on the Templates page
</script>

<template>
  <div class="bs-launch">
    <div class="bs-launch__form">
      <AppField v-model="name" class="lp-name" :label="t('landing.launch.name')" :placeholder="t('landing.launch.placeholder')" autocomplete="off" />
    </div>

    <ThemePreviewPane :theme="theme" :name="shown" :mode="ui.mode" />

    <AppButton to="/templates" icon="arrow" size="lg" block>{{ t('landing.launch.go') }}</AppButton>
  </div>
</template>

<style scoped>
/* The association name box is the one field the visitor meets first: a little taller, with larger text (W25-R47). */
.lp-name :deep(.rs-input) { min-height: 46px; font-size: 16px; }
</style>
