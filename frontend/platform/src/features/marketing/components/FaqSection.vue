<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { faqIds } from '@/mock/marketing'

// Pricing FAQ, design v4 (.bp-faq): two columns on wide containers, one on narrow ones; hairline between the questions.
const { t } = useI18n()
</script>

<template>
  <section class="bp-faq" :aria-label="t('marketing.faq.title')">
    <div v-for="q in faqIds" :key="q"><b>{{ t(`marketing.faq.q${q}`) }}</b><span>{{ t(`marketing.faq.a${q}`) }}</span></div>
  </section>
</template>
