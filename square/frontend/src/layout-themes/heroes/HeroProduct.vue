<script setup lang="ts">
import { eventsOn, dayMonth } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import { useLookup } from '../../composables/useLookup'
import LtCtas from '../parts/LtCtas.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtStats from '../parts/LtStats.vue'
import LtUpNext from '../parts/LtUpNext.vue'

// Product hero: a 12-column grid behind the text, the square's own small labels as chips, and the next three events stacked like cards in an app (W9-R9).
const { home, events } = useSiteData()
const { label: typeLabel } = useLookup('event_type')
</script>

<template>
  <section class="lt-hero lt-h-product">
    <div class="lt-cont">
      <div class="lt-split lt-split-product">
        <div class="lt-stack">
          <div v-if="home.eyebrow || home.utility_text" class="lt-chips"><span v-for="(c, i) in [home.eyebrow, home.utility_text].filter(Boolean)" :key="c" class="lt-chip" :class="{ 'lt-chip-hi': i === 0 }">{{ c }}</span></div>
          <LtHeadline />
          <LtLead />
          <LtCtas />
        </div>
        <div v-if="eventsOn && events.length" class="lt-pr-stack">
          <router-link v-for="(e, i) in events.slice(0, 3)" :key="e.id" :to="`/events/${e.slug}`" class="lt-pr-card" :style="{ '--i': i }">
            <span class="lt-pr-day"><b>{{ dayMonth(e.start_datetime).day }}</b><i>{{ dayMonth(e.start_datetime).month.toUpperCase() }}</i></span>
            <span class="lt-pr-ttl"><strong>{{ e.title }}</strong><small v-if="e.venue">{{ e.venue }}</small></span>
            <span class="lt-chip">{{ typeLabel(e.event_type) }}</span>
          </router-link>
        </div>
        <LtUpNext v-else />
      </div>
      <LtStats class="lt-rule-top" />
    </div>
  </section>
</template>
