<script setup lang="ts">
import { useSiteData } from '../useSiteData'
import LtCtas from '../parts/LtCtas.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtStats from '../parts/LtStats.vue'
import LtUpNext from '../parts/LtUpNext.vue'

// Softform hero: a big pressed card with soft colour shapes, and a column with the next event and a photo (W9-R9).
const { home, heroMain } = useSiteData()
</script>

<template>
  <section class="lt-hero lt-h-softgrid">
    <div class="lt-cont">
      <div class="lt-sg-grid">
        <div class="lt-sg-card lt-nu-12">
          <span class="lt-sg-blob" aria-hidden="true" />
          <span class="lt-sg-dot" aria-hidden="true" />
          <div class="lt-stack lt-sg-text">
            <span v-if="home.eyebrow" class="lt-eyebrow">{{ home.eyebrow }}</span>
            <LtHeadline />
            <LtLead />
            <LtCtas />
          </div>
        </div>
        <div class="lt-sg-side">
          <LtUpNext class="lt-sg-up" />
          <LtPhoto :src="heroMain" alt="" class="lt-sg-photo lt-nu-10" />
        </div>
      </div>
      <LtStats class="lt-sg-stats" />
    </div>
  </section>
</template>
