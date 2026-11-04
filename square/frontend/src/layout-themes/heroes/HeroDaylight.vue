<script setup lang="ts">
import { computed } from 'vue'
import { eventsOn, cta, dayMonth } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import LtButton from '../parts/LtButton.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import { formatEventDate } from '../../utils/date'

// Daylight hero: the headline, then a lavender panel with the next event and a photo, beside a calendar of the week the next event falls in. The
// days with an event are marked from the square's real events (W9-R9).
const { home, events, nextEvent, heroMain } = useSiteData()
const WD = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
const day0 = computed(() => {
  if (!nextEvent.value) return null
  const d = new Date(nextEvent.value.start_datetime)
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7)) // the Monday of that week
  return d
})
const days = computed(() => {
  if (!day0.value) return []
  const marked = new Set(events.value.map((e) => new Date(e.start_datetime).toDateString()))
  return WD.map((w, i) => {
    const d = new Date(day0.value!)
    d.setDate(d.getDate() + i)
    return { w, n: d.getDate(), on: marked.has(d.toDateString()) }
  })
})
const range = computed(() => (days.value.length && day0.value ? `${dayMonth(day0.value.toISOString()).month} ${days.value[0]!.n} – ${days.value[6]!.n}` : ''))
const ordinal = (n: number) => `${n}${[11, 12, 13].includes(n % 100) ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th'}`
</script>

<template>
  <section class="lt-hero lt-h-daylight">
    <div class="lt-cont">
      <div class="lt-stack lt-dl-head">
        <span v-if="home.eyebrow" class="lt-eyebrow lt-eyebrow-mute">{{ home.eyebrow }}</span>
        <LtHeadline />
        <LtLead />
      </div>
      <div class="lt-dl-grid" :class="{ 'lt-dl-one': !(eventsOn && nextEvent) }">
        <div class="lt-dl-panel">
          <template v-if="eventsOn && nextEvent">
            <small>UP NEXT · {{ dayMonth(nextEvent.start_datetime).day }} {{ dayMonth(nextEvent.start_datetime).month.toUpperCase() }}</small>
            <strong>{{ nextEvent.title }}</strong>
            <span>{{ formatEventDate(nextEvent.start_datetime) }}<template v-if="nextEvent.venue"> · {{ nextEvent.venue }}</template></span>
          </template>
          <strong v-else>{{ cta.label }}</strong>
          <LtPhoto :src="heroMain" alt="" ratio="16 / 6" class="lt-dl-photo" />
          <div><LtButton :to="eventsOn && nextEvent ? `/events/${nextEvent.slug}` : cta.to">{{ eventsOn && nextEvent ? 'Reserve a seat' : cta.label }}</LtButton></div>
        </div>
        <div v-if="eventsOn && nextEvent && days.length" class="lt-dl-week">
          <div class="lt-dl-wk-h"><strong>This week</strong><span>{{ range }}</span></div>
          <div class="lt-dl-days"><span v-for="(d, i) in days" :key="i"><i>{{ d.w }}</i><b :class="{ 'is-on': d.on }">{{ d.on ? '✓' : d.n }}</b></span></div>
          <p>{{ nextEvent.title }} falls on the {{ ordinal(new Date(nextEvent.start_datetime).getDate()) }}.</p>
        </div>
      </div>
      <div v-if="home.stats.length" class="lt-dl-stats"><div v-for="s in home.stats" :key="s.label"><b>{{ s.value }}</b><span>{{ s.label }}</span></div></div>
    </div>
  </section>
</template>
