<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useSite } from './useSite'
import TButton from './components/TButton.vue'

// Tenant 404 (design "404, maintenance"): big display number in the link colour, title, text, home button.
const { t } = useI18n()
const { to } = useSite()
</script>

<template>
  <section class="t-center">
    <div class="t-wrap t-center__in">
      <div class="t-404">404</div>
      <h1 style="font-size: clamp(28px, 4vw, 36px)">{{ t('site.nf.title') }}</h1>
      <p style="margin: 0">{{ t('site.nf.text') }}</p>
      <TButton :to="to('')">{{ t('site.nf.home') }}</TButton>
    </div>
  </section>
</template>
