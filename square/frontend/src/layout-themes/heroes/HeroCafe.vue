<script setup lang="ts">
import { useSiteData } from '../useSiteData'
import LtCtas from '../parts/LtCtas.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'

// Sage Café hero: a green panel with one rounded corner, a blob-shaped photo, and the numbers as round badges below (W9-R9).
const { home, heroMain } = useSiteData()
</script>

<template>
  <section class="lt-hero lt-h-cafe">
    <div class="lt-cafe-wrap">
      <div class="lt-cafe-panel lt-on-panel">
        <div class="lt-stack lt-cafe-text">
          <LtHeadline />
          <LtLead />
          <LtCtas />
        </div>
        <div class="lt-cafe-pic"><LtPhoto :src="heroMain" alt="" class="lt-cafe-photo" /></div>
      </div>
      <div v-if="home.stats.length" class="lt-cafe-stats">
        <div v-for="s in home.stats" :key="s.label"><span class="lt-cafe-badge">{{ s.value }}</span><b>{{ s.label }}</b></div>
      </div>
    </div>
  </section>
</template>
