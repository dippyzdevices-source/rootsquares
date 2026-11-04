<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import Wordmark from '@rootsquares/ui/components/Wordmark.vue'

// The footer of the public site and the platform pages (W11-R49): the layout of the BCA Oslo footer (brand and words on the left, link columns on the right,
// an ornament, the copyright line) in the platform's own words. Dark band in both themes. Only what exists is shown: no registration line, social links,
// contact e-mail yet (the platform has none of them; docs/OPEN_QUESTIONS.md). Privacy and Terms are placeholders without legal text (W13-R49).
const { t } = useI18n()
const product = [
  { to: '/#features', key: 'nav.features' },
  { to: '/pricing', key: 'nav.pricing' },
  { to: '/templates', key: 'nav.templates' },
  { to: '/case-study/bca', key: 'nav.caseStudies' },
]
</script>

<template>
  <footer class="lr-foot">
    <div class="lr-foot__top">
      <div class="lr-foot__brand">
        <RouterLink to="/" class="lr-foot__logo" :aria-label="t('footer.home')"><Wordmark :size="32" /></RouterLink>
        <p>{{ t('footer.tagline') }}</p>
      </div>
      <div class="lr-foot__cols">
        <nav :aria-label="t('footer.product')">
          <span class="lr-foot__h">{{ t('footer.product') }}</span>
          <RouterLink v-for="l in product" :key="l.to" :to="l.to">{{ t(l.key) }}</RouterLink>
        </nav>
        <nav :aria-label="t('footer.touch')">
          <span class="lr-foot__h">{{ t('footer.touch') }}</span>
          <RouterLink to="/contact">{{ t('footer.contactPage') }}</RouterLink>
        </nav>
        <nav :aria-label="t('footer.legal')">
          <span class="lr-foot__h">{{ t('footer.legal') }}</span>
          <RouterLink to="/privacy">{{ t('footer.privacy') }}</RouterLink>
          <RouterLink to="/terms">{{ t('footer.terms') }}</RouterLink>
        </nav>
      </div>
    </div>
    <div class="lr-foot__orn" aria-hidden="true"><i /></div>
    <div class="lr-foot__bot"><span>{{ t('footer.copy') }}</span><span>{{ t('footer.nordics') }}</span></div>
  </footer>
</template>
