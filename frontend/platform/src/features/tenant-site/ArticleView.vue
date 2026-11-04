<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { articles } from '@/mock/bca'
import { useSite } from './useSite'
import TPlaceholder from './components/TPlaceholder.vue'
import TButton from './components/TButton.vue'

// Article page (design "Article list/page"): measure capped at 62ch, pull quote with a link-coloured rule.
const { t } = useI18n()
const route = useRoute()
const { to } = useSite()
const a = computed(() => articles.find((x) => x.id === route.params.articleId))
</script>

<template>
  <article class="t-sec">
    <div class="t-wrap t-stack" style="max-width: 760px; gap: 20px">
      <RouterLink :to="to('/news')" class="t-uline" style="align-self: flex-start">← {{ t('site.news.back') }}</RouterLink>
      <template v-if="a">
        <span class="t-eyebrow">{{ a.kicker }}</span>
        <h1 style="font-size: clamp(32px, 5vw, 46px); line-height: 1.1">{{ a.title }}</h1>
        <TPlaceholder ratio="16/9" shape="lg" :label="t('site.news.cover')" />
        <p class="t-lead" style="max-width: 62ch">{{ a.paragraphs[0] }}</p>
        <blockquote class="t-quote">{{ a.quote }}</blockquote>
        <p class="t-lead" style="max-width: 62ch">{{ a.paragraphs[1] }}</p>
      </template>
      <template v-else><h1 style="font-size: 32px">{{ t('site.notFound') }}</h1><TButton variant="outline" :to="to('/news')">{{ t('site.news.back') }}</TButton></template>
    </div>
  </article>
</template>
