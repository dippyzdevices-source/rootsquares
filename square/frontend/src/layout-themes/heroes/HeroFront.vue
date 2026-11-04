<script setup lang="ts">
import { computed } from 'vue'
import { dayMonth, eventsOn, navItems } from '../useSiteLayout'
import { useSiteData } from '../useSiteData'
import LtCtas from '../parts/LtCtas.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtPhoto from '../parts/LtPhoto.vue'

// Ledger hero: the front page of a newspaper. A lead story with a drop cap, and a side column with "In this issue", a notice and the numbers (W9-R5).
const { home, heroMain, nextEvent } = useSiteData()
const index = navItems.filter((n) => n.key !== 'home')
const lead = computed(() => [home.value.intro, home.value.intro_suffix].filter(Boolean).join(' ').trim())
const when = computed(() => (nextEvent.value ? dayMonth(nextEvent.value.start_datetime) : null))
</script>

<template>
  <section class="lt-hero lt-h-front">
    <div class="lt-cont">
      <div class="lt-front">
        <div class="lt-front-lead">
          <span class="lt-kick lt-kick-caps">{{ home.eyebrow || 'Lead story' }}</span>
          <LtHeadline />
          <p v-if="home.local_line" class="lt-front-by ds-bn">{{ home.local_line }}</p>
          <LtPhoto :src="heroMain" alt="" ratio="16 / 8" radius="0" />
          <p v-if="lead" class="lt-front-body"><span class="lt-dropcap" aria-hidden="true">{{ lead.charAt(0) }}</span><span class="lt-sr">{{ lead.charAt(0) }}</span>{{ lead.slice(1) }}</p>
          <LtCtas />
        </div>
        <aside class="lt-front-side">
          <div>
            <h2 class="lt-front-h">In this issue</h2>
            <router-link v-for="n in index" :key="n.key" :to="n.to" class="lt-front-row"><span>{{ n.label }}</span><i aria-hidden="true" /><b>→</b></router-link>
          </div>
          <router-link v-if="eventsOn && nextEvent && when" :to="`/events/${nextEvent.slug}`" class="lt-front-note">
            <small class="lt-kick lt-kick-caps">Notice · Up next</small>
            <strong>{{ nextEvent.title }}</strong>
            <span class="lt-mute">{{ when.day }} {{ when.month }}<template v-if="nextEvent.venue"> · {{ nextEvent.venue }}</template></span>
          </router-link>
          <div v-if="home.stats.length" class="lt-front-stats">
            <div v-for="s in home.stats" :key="s.label"><span class="lt-mute">{{ s.label }}</span><b>{{ s.value }}</b></div>
          </div>
        </aside>
      </div>
    </div>
  </section>
</template>
