<script setup lang="ts">
import { computed } from 'vue'
import { dayMonth, eventsOn, galleryOn } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import LtCtas from '../parts/LtCtas.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtUpNext from '../parts/LtUpNext.vue'
import { formatEventDate } from '../../utils/date'

// Sand & Teal hero: text on the left, and on the right one pressed panel holding the next event, two photos and the numbers, each in its own recess (W9-R9).
const { home, nextEvent, heroMain, heroThumbs } = useSiteData()
const when = computed(() => (nextEvent.value ? dayMonth(nextEvent.value.start_datetime) : null))
</script>

<template>
  <section class="lt-hero lt-h-emboss">
    <div class="lt-cont">
      <div class="lt-split lt-split-emboss">
        <div class="lt-stack">
          <span v-if="home.eyebrow" class="lt-eyebrow">{{ home.eyebrow }}</span>
          <LtHeadline />
          <LtLead />
          <LtCtas />
        </div>
        <div class="lt-em-panel lt-nu-14">
          <router-link v-if="eventsOn && nextEvent && when" :to="`/events/${nextEvent.slug}`" class="lt-em-next lt-nui-8">
            <small>UP NEXT</small>
            <strong>{{ nextEvent.title }}</strong>
            <span>{{ formatEventDate(nextEvent.start_datetime) }}<template v-if="nextEvent.venue"> · {{ nextEvent.venue }}</template></span>
          </router-link>
          <LtUpNext v-else />
          <div v-if="galleryOn" class="lt-em-photos">
            <div class="lt-nu-6"><LtPhoto :src="heroMain" alt="" ratio="1 / 0.8" /></div>
            <div class="lt-nu-6"><LtPhoto :src="heroThumbs[0]?.thumbnail_url" alt="" ratio="1 / 0.8" /></div>
          </div>
          <div v-if="home.stats.length" class="lt-em-stats">
            <div v-for="s in home.stats" :key="s.label" class="lt-nui-6"><b>{{ s.value }}</b><span>{{ s.label }}</span></div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
