<script setup lang="ts">
import { useSiteData } from '../useSiteData'
import LtCtas from '../parts/LtCtas.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtStats from '../parts/LtStats.vue'
import LtUpNext from '../parts/LtUpNext.vue'

// Harvest Hall hero: text left, a framed photo right with the Up next card overlapping its corner (W9-R5).
const { home, heroMain } = useSiteData()
</script>

<template>
  <section class="lt-hero lt-h-asym">
    <div class="lt-cont">
      <div class="lt-split lt-split-asym">
        <div class="lt-stack">
          <span v-if="home.eyebrow" class="lt-eyebrow">{{ home.eyebrow }}</span>
          <LtHeadline />
          <LtLead />
          <LtCtas />
        </div>
        <div class="lt-asym-pic">
          <span class="lt-asym-frame" aria-hidden="true" />
          <LtPhoto :src="heroMain" alt="" ratio="4 / 5" class="lt-asym-photo" />
          <LtUpNext class="lt-asym-up" />
        </div>
      </div>
      <LtStats class="lt-rule-top" />
    </div>
  </section>
</template>
