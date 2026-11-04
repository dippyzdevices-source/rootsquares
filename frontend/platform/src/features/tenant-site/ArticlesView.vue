<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { articles } from '@/mock/bca'
import { useSite } from './useSite'
import TPlaceholder from './components/TPlaceholder.vue'

// Article list (design "Article list/page"): cover placeholder, kicker, title, excerpt, read more. Content is mock (English only).
const { t } = useI18n()
const { to } = useSite()
</script>

<template>
  <section class="t-sec">
    <div class="t-wrap">
      <h1 style="font-size: clamp(32px, 5vw, 48px)">{{ t('site.news.title') }}</h1>
      <p class="t-muted" style="margin: 8px 0 24px">{{ t('site.news.lead') }}</p>
      <div class="t-events-grid">
        <article v-for="a in articles" :key="a.id" class="t-event">
          <TPlaceholder ratio="3/2" shape="none" :label="t('site.news.cover')" />
          <div class="t-event__body">
            <span class="t-eyebrow">{{ a.kicker }}</span>
            <h3 style="font-size: 21px; line-height: 1.2; margin: 0"><RouterLink :to="to(`/news/${a.id}`)" class="t-plainlink">{{ a.title }}</RouterLink></h3>
            <p style="margin: 0; font-size: 15px">{{ a.excerpt }}</p>
            <RouterLink :to="to(`/news/${a.id}`)" class="t-uline">{{ t('site.news.read') }}</RouterLink>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>
