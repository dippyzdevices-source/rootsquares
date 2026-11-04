<script setup lang="ts">
import { eventsOn, dayMonth, navItems } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import { cta, cta2 } from '../useSiteLayout'
import LtButton from '../parts/LtButton.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtStats from '../parts/LtStats.vue'

// Pearl hero: one centred pressed card, a pressed row of quick links, then the next three events as small cards (W9-R9).
const { home, events } = useSiteData()
const jump = navItems.slice(1, 5)
</script>

<template>
  <section class="lt-hero lt-h-pearl">
    <div class="lt-cont">
      <div class="lt-pe-card lt-nu-14">
        <span v-if="home.eyebrow" class="lt-eyebrow">{{ home.eyebrow }}</span>
        <LtHeadline />
        <LtLead />
        <div class="lt-ctas lt-ctas-center"><LtButton :to="cta.to">{{ cta.label }}</LtButton><LtButton :to="cta2.to" kind="o">{{ cta2.label }} →</LtButton></div>
        <nav aria-label="Quick links" class="lt-pe-jump lt-nui-6"><router-link v-for="n in jump" :key="n.key" :to="n.to">{{ n.label }}</router-link></nav>
      </div>
      <div v-if="eventsOn && events.length" class="lt-pe-events">
        <router-link v-for="e in events.slice(0, 3)" :key="e.id" :to="`/events/${e.slug}`" class="lt-pe-ev lt-nu">
          <span class="lt-pe-day"><b>{{ dayMonth(e.start_datetime).day }}</b><i>{{ dayMonth(e.start_datetime).month.toUpperCase() }}</i></span>
          <span class="lt-pe-ttl"><strong>{{ e.title }}</strong><small v-if="e.venue">{{ e.venue }}</small></span>
        </router-link>
      </div>
      <LtStats class="lt-stats-center" />
    </div>
  </section>
</template>
