<script setup lang="ts">
import { computed } from 'vue'
import { cta, eventsOn, dayMonth, membershipOn } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import LtCtas from '../parts/LtCtas.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import { galleryOn } from '../useSiteLayout'

// Fjord Modern hero: a huge headline, then a row of three blocks: photo, an accent block with the next event, and a second photo (W9-R5).
const { home, heroMain, heroThumbs, nextEvent } = useSiteData()
const when = computed(() => (nextEvent.value ? dayMonth(nextEvent.value.start_datetime) : null))
const second = computed(() => heroThumbs.value[0]?.thumbnail_url)
</script>

<template>
  <section class="lt-hero lt-h-swiss">
    <div class="lt-cont">
      <div class="lt-swiss-top">
        <LtHeadline />
        <div class="lt-stack lt-swiss-side">
          <span v-if="home.eyebrow || home.utility_text" class="lt-eyebrow">{{ home.eyebrow || home.utility_text }}</span>
          <LtLead />
          <LtCtas />
        </div>
      </div>
      <div class="lt-swiss-row">
        <LtPhoto :src="heroMain" alt="" class="lt-swiss-ph" />
        <router-link v-if="(eventsOn && nextEvent && when) || membershipOn" :to="eventsOn && nextEvent ? `/events/${nextEvent.slug}` : cta.to" class="lt-swiss-acc">
          <small>{{ eventsOn && nextEvent ? 'UP NEXT' : 'JOIN' }}</small>
          <span v-if="eventsOn && nextEvent && when"><b>{{ when.day }}</b><i>{{ when.month }} {{ when.year }}</i><strong>{{ nextEvent.title }}</strong></span>
          <span v-else><strong>{{ cta.label }}</strong></span>
        </router-link>
        <LtPhoto v-if="galleryOn" :src="second" alt="" class="lt-swiss-ph" />
        <div v-else-if="home.local_line" class="lt-swiss-note ds-bn">{{ home.local_line }}</div>
      </div>
    </div>
  </section>
</template>
