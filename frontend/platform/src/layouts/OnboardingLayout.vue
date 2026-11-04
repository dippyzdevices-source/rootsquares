<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// Wizard chrome (design v4): the wizard draws its own rail, progress bar and footer, so the layout only holds the page container and the skip link.
const { t } = useI18n()
</script>

<template>
  <div class="rs-appwrap">
    <a href="#main" class="rs-sr">{{ t('app.skipToContent') }}</a>
    <RouterView />
  </div>
</template>
