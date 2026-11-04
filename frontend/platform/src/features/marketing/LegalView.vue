<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppAlert from '@rootsquares/ui/components/AppAlert.vue'

// Placeholder for the platform's Privacy and Terms pages (W13-R49): /privacy and /terms. There is no legal text yet (it waits for a lawyer: docs/LEGAL_TODO.md),
// so each page says so plainly and lists only the topics it will cover. It states nothing about the law. Built from the Contact page's classes; no new styles.
const { t } = useI18n()
const route = useRoute()
const kind = computed(() => (route.name === 'terms' ? 'terms' : 'privacy') as 'privacy' | 'terms')
const topics = [1, 2, 3, 4, 5]
</script>

<template>
  <article style="display: grid; gap: 16px; max-width: 720px; margin: 0 auto; align-content: start" :data-testid="`legal-${kind}`">
    <span class="rs-eyebrow">{{ t('marketing.legal.eyebrow') }}</span>
    <h1 class="bs-d" style="font-size: 48px">{{ t(`marketing.legal.${kind}.title`) }}</h1>
    <AppAlert tone="info" :title="t('marketing.legal.draftTitle')">{{ t('marketing.legal.draftText') }}</AppAlert>
    <p class="bs-mute" style="margin: 0">{{ t(`marketing.legal.${kind}.lede`) }}</p>
    <h2 class="bs-h2" style="font-size: 24px; margin: 8px 0 0">{{ t('marketing.legal.topics') }}</h2>
    <ul style="margin: 0; padding-left: 20px; display: grid; gap: 6px">
      <li v-for="n in topics" :key="n">{{ t(`marketing.legal.${kind}.t${n}`) }}</li>
    </ul>
    <p class="bs-mute" style="margin: 0; font-size: var(--text-sm)">{{ t('marketing.legal.ask') }} <RouterLink to="/contact">{{ t('footer.contactPage') }}</RouterLink></p>
  </article>
</template>
