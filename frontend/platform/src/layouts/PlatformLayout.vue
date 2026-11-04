<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import SiteHeader from '@/components/ui/SiteHeader.vue'
import SiteFooter from '@/components/ui/SiteFooter.vue'

// Public site and platform pages: the shared header (SiteHeader), the page, and the footer (SiteFooter, W11-R49).
const { t } = useI18n()
</script>

<template>
  <div class="rs-appwrap">
    <div class="mk">
      <a href="#main" class="rs-sr">{{ t('app.skipToContent') }}</a>
      <SiteHeader />
      <main id="main"><RouterView /></main>
      <SiteFooter />
    </div>
  </div>
</template>
