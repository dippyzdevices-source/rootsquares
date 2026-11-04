<script setup lang="ts">
import { computed } from 'vue'
import { cta, cta2 } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import { tornPolygon } from '../useShellBits'
import LtButton from '../parts/LtButton.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtStats from '../parts/LtStats.vue'
import LtUpNext from '../parts/LtUpNext.vue'

// Torn Paper hero: a coloured sheet with a torn lower edge, the headline large, and a round photo with the next event on it (W9-R9).
const { heroMain } = useSiteData()
const edge = computed(() => tornPolygon(5))
</script>

<template>
  <section class="lt-hero lt-h-torn lt-on-panel" :style="{ clipPath: edge }">
    <div class="lt-cont">
      <div class="lt-split lt-split-torn">
        <div class="lt-stack">
          <LtHeadline />
          <LtLead />
          <div class="lt-ctas"><LtButton :to="cta.to" kind="a">{{ cta.label }}</LtButton><LtButton :to="cta2.to" kind="ow">{{ cta2.label }} →</LtButton></div>
        </div>
        <div class="lt-torn-pic">
          <LtPhoto :src="heroMain" alt="" ratio="1" class="lt-torn-photo" />
          <LtUpNext class="lt-torn-up" />
        </div>
      </div>
      <LtStats class="lt-torn-stats" />
    </div>
  </section>
</template>
