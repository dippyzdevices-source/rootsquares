<script setup lang="ts">
import { computed } from 'vue'
import { cta, cta2, dayMonth, eventsOn } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtStats from '../parts/LtStats.vue'

// Stillwater hero: centred and quiet, two italic text links, one wide photo, the next gathering as a single line (W9-R5).
const { home, heroMain, nextEvent } = useSiteData()
const when = computed(() => (nextEvent.value ? dayMonth(nextEvent.value.start_datetime) : null))
</script>

<template>
  <section class="lt-hero lt-h-quiet">
    <div class="lt-cont lt-center-col">
      <span v-if="home.utility_text || home.eyebrow" class="lt-eyebrow lt-eyebrow-mute">{{ home.eyebrow || home.utility_text }}</span>
      <LtHeadline />
      <LtLead />
      <div class="lt-links">
        <router-link :to="cta.to" class="lt-link-it">{{ cta.label }} →</router-link>
        <router-link :to="cta2.to" class="lt-link-it">{{ cta2.label }}</router-link>
      </div>
    </div>
    <div class="lt-quiet-pic"><LtPhoto :src="heroMain" alt="" ratio="21 / 8" /></div>
    <div class="lt-cont lt-center-col">
      <router-link v-if="eventsOn && nextEvent && when" :to="`/events/${nextEvent.slug}`" class="lt-nextline">
        Next gathering — <span>{{ nextEvent.title }}</span>, {{ when.day }} {{ when.month }}<template v-if="nextEvent.venue">, {{ nextEvent.venue }}</template>
      </router-link>
      <LtStats class="lt-stats-center" />
    </div>
  </section>
</template>
