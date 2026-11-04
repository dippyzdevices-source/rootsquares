<script setup lang="ts">
import { compact } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import LtCtas from '../parts/LtCtas.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtStats from '../parts/LtStats.vue'
import LtUpNext from '../parts/LtUpNext.vue'

// Berry Courtyard hero: a wide photo with a card overlapping its lower edge; the numbers sit beneath (W9-R5). The Up next card lives in the side panel on a wide site.
const { home, heroMain } = useSiteData()
</script>

<template>
  <section class="lt-hero lt-h-berry">
    <div class="lt-cont">
      <LtPhoto :src="heroMain" alt="" ratio="16 / 9" class="lt-berry-photo" />
      <div class="lt-berry-card lt-stack">
        <span v-if="home.eyebrow" class="lt-eyebrow">{{ home.eyebrow }}</span>
        <LtHeadline />
        <LtLead />
        <LtCtas />
        <LtUpNext v-if="compact" />
      </div>
      <LtStats class="lt-berry-stats" />
    </div>
  </section>
</template>
