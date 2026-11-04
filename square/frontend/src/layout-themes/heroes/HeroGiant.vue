<script setup lang="ts">
import { computed } from 'vue'
import { dayMonth, eventsOn } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import { headlineParts } from '../useSiteLayout'
import { squareProfile } from '../../services/squareConfig'
import LtCtas from '../parts/LtCtas.vue'
import LtLead from '../parts/LtLead.vue'
import LtStats from '../parts/LtStats.vue'
import LtUpNext from '../parts/LtUpNext.vue'

// Marquee hero: the headline in giant capitals on up to three lines, a ticker of coming events (still when the visitor prefers less motion), then the lead (W9-R5).
const { home, events } = useSiteData()
const parts = computed(() => headlineParts(home.value.headline || squareProfile.name))
const ticker = computed(() => {
  const items = eventsOn && events.value.length ? events.value.map((e) => `${e.title} — ${dayMonth(e.start_datetime).day} ${dayMonth(e.start_datetime).month}`) : [squareProfile.name, home.value.tagline_local].filter(Boolean)
  return [...items, ...items]
})
</script>

<template>
  <section class="lt-hero lt-h-giant">
    <div class="lt-cont">
      <h1 class="lt-giant-h1">
        <span v-if="parts[0]">{{ parts[0] }}</span>
        <span v-if="parts[1]" class="lt-giant-acc">{{ parts[1] }}</span>
        <span v-if="parts[2]">{{ parts[2] }}</span>
      </h1>
    </div>
    <div class="lt-ticker" aria-hidden="true"><div class="lt-ticker-track"><span v-for="(t, i) in ticker" :key="i">{{ t }}  ✦</span></div></div>
    <div class="lt-cont">
      <div class="lt-giant-row">
        <div class="lt-stack"><LtLead /><LtCtas /></div>
        <LtUpNext class="lt-giant-up" />
      </div>
      <LtStats />
    </div>
  </section>
</template>
