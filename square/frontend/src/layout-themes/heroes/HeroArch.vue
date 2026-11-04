<script setup lang="ts">
import { galleryOn } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import LtCtas from '../parts/LtCtas.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtStats from '../parts/LtStats.vue'
import LtUpNext from '../parts/LtUpNext.vue'

// Olive & Linen hero: a rounded panel with the text on the left and an arched photo on the right; small photos tuck under it (W9-R5).
const { home, heroMain, heroThumbs } = useSiteData()
</script>

<template>
  <section class="lt-hero lt-h-arch">
    <div class="lt-cont">
      <div class="lt-arch-panel">
        <div class="lt-stack">
          <span v-if="home.eyebrow" class="lt-eyebrow">{{ home.eyebrow }}</span>
          <LtHeadline />
          <LtLead />
          <LtCtas />
          <LtUpNext class="lt-arch-up" />
        </div>
        <div class="lt-arch-pic">
          <LtPhoto :src="heroMain" alt="" ratio="4 / 5" class="lt-arch-photo" />
          <div v-if="galleryOn && heroThumbs.length" class="lt-arch-thumbs">
            <LtPhoto v-for="m in heroThumbs.slice(0, 2)" :key="m.id" :src="m.thumbnail_url" alt="" ratio="1 / 0.8" />
          </div>
        </div>
      </div>
      <LtStats class="lt-stats-center" />
    </div>
  </section>
</template>
