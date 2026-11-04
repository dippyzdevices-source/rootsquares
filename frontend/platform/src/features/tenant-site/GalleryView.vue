<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { photoLabels } from '@/mock/bca'
import TLightbox from './components/TLightbox.vue'
import TPlaceholder from './components/TPlaceholder.vue'

// Photo grid with the design's lightbox (focus trap, Esc, arrow keys).
const { t } = useI18n()
const current = ref<number | null>(null)
</script>

<template>
  <section class="t-sec">
    <div class="t-wrap">
      <h1 style="font-size: clamp(32px, 5vw, 48px)">{{ t('site.galleryTitle') }}</h1>
      <p class="t-muted" style="margin: 8px 0 24px">{{ t('site.galleryText') }}</p>
      <div class="t-gallery">
        <button v-for="(l, i) in photoLabels" :key="l" type="button" :aria-label="`${t('site.photo', { n: i + 1 })}: ${l}`" @click="current = i"><TPlaceholder ratio="1/1" shape="md" :label="l" /></button>
      </div>
    </div>
  </section>
  <TLightbox v-if="current !== null" v-model:index="current" :labels="photoLabels" @close="current = null" />
</template>
