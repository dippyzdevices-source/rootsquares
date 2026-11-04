<script setup lang="ts">
import { useSiteData } from '../useSiteData'
import { cta, cta2 } from '../useSiteLayout'
import LtButton from '../parts/LtButton.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtStats from '../parts/LtStats.vue'
import LtUpNext from '../parts/LtUpNext.vue'

// Canopy Grove hero: a deep green panel with a leaf shape behind the text and a leaf-cornered photo (W9-R9).
const { home, heroMain } = useSiteData()
</script>

<template>
  <section class="lt-hero lt-h-leaf">
    <div class="lt-leaf-panel lt-on-panel">
      <span class="lt-leaf-shape" aria-hidden="true" />
      <div class="lt-leaf-grid">
        <div class="lt-stack">
          <span v-if="home.eyebrow" class="lt-eyebrow lt-eyebrow-pa">{{ home.eyebrow }}</span>
          <LtHeadline />
          <LtLead />
          <div class="lt-ctas"><LtButton :to="cta.to" kind="a">{{ cta.label }}</LtButton><LtButton :to="cta2.to" kind="ow">{{ cta2.label }} →</LtButton></div>
        </div>
        <div class="lt-leaf-pic">
          <LtPhoto :src="heroMain" alt="" ratio="4 / 5" class="lt-leaf-photo" />
          <LtUpNext class="lt-leaf-up" />
        </div>
      </div>
    </div>
    <div class="lt-cont"><LtStats class="lt-stats-center" /></div>
  </section>
</template>
