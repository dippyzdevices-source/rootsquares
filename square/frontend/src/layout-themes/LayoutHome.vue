<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, type Component } from 'vue'
import { useLookup } from '../composables/useLookup'
import SponsorsMarquee from '../components/SponsorsMarquee.vue'
import { moduleEnabled } from '../services/modules'
import { squareProfile } from '../services/squareConfig'
import { activeLayout, type HeroKind, type SectionKey } from './layouts'
import { sectionOn, testimonialsOn } from './useSiteLayout'
import { ensureHome, useSiteData } from './useSiteData'
import EventsBlock from './sections/EventsBlock.vue'
import GalleryBlock from './sections/GalleryBlock.vue'
import HeritageBlock from './sections/HeritageBlock.vue'
import MembershipBlock from './sections/MembershipBlock.vue'
import NewsBlock from './sections/NewsBlock.vue'
import SectionHead from './parts/SectionHead.vue'
import LtQuoteNav from './parts/LtQuoteNav.vue'

// The home page of a themed square (W9-R5): the theme's hero, then the sections in the theme's order. A section whose module is off is not
// there at all (no gap, no divider); the heroes and the neighbours reflow. Words come from the square (Settings, Content); neutral text otherwise.
const layout = activeLayout!
const HEROES: Partial<Record<HeroKind, Component>> = {
  asym: defineAsyncComponent(() => import('./heroes/HeroAsym.vue')),
  quiet: defineAsyncComponent(() => import('./heroes/HeroQuiet.vue')),
  swiss: defineAsyncComponent(() => import('./heroes/HeroSwiss.vue')),
  zine: defineAsyncComponent(() => import('./heroes/HeroZine.vue')),
  arch: defineAsyncComponent(() => import('./heroes/HeroArch.vue')),
  berry: defineAsyncComponent(() => import('./heroes/HeroBerry.vue')),
  front: defineAsyncComponent(() => import('./heroes/HeroFront.vue')),
  giant: defineAsyncComponent(() => import('./heroes/HeroGiant.vue')),
  leaf: defineAsyncComponent(() => import('./heroes/HeroLeaf.vue')),
  softgrid: defineAsyncComponent(() => import('./heroes/HeroSoftgrid.vue')),
  emboss: defineAsyncComponent(() => import('./heroes/HeroEmboss.vue')),
  pearl: defineAsyncComponent(() => import('./heroes/HeroPearl.vue')),
  product: defineAsyncComponent(() => import('./heroes/HeroProduct.vue')),
  daylight: defineAsyncComponent(() => import('./heroes/HeroDaylight.vue')),
  torn: defineAsyncComponent(() => import('./heroes/HeroTorn.vue')),
  cafe: defineAsyncComponent(() => import('./heroes/HeroCafe.vue')),
}
const hero = HEROES[layout.hero]!
const { home, events, media, news, tiers, aboutText, quote } = useSiteData()
onMounted(ensureHome)

const name = squareProfile.name
const META: Record<SectionKey, { title: string; sub: string; link: [string, string] | null }> = {
  events: { title: 'Events', sub: "What's on this season", link: ['All events', '/events'] },
  heritage: { title: 'About', sub: `About ${name}`, link: ['Our story', '/about'] },
  gallery: { title: 'Gallery', sub: `Moments from ${name}`, link: ['All photos', '/gallery'] },
  news: { title: 'News', sub: 'News and notices', link: ['All news', '/news'] },
  membership: { title: 'Membership', sub: 'Become a member', link: null },
}
const meta = (key: SectionKey) => {
  const own = home.value.page_headings[key]
  return { ...META[key], title: own?.title || META[key].title, sub: own?.intro || META[key].sub }
}
const hasHeritage = computed(() => !!(home.value.about_page.timeline.length || aboutText.value.trim() || home.value.blurb.trim()))
const sections = computed(() => layout.order.filter((k) => sectionOn(k) && (k !== 'heritage' || hasHeritage.value) && (k !== 'membership' || tiers.value.length > 0)))
const showQuote = computed(() => testimonialsOn && quote.value)
// The programme filters of the default home page: All events and one pill per event type (W10-R7).
const { options: eventTypes } = useLookup('event_type')
const pick = ref('')
const pills = computed(() => [{ value: '', label: 'All events' }, ...eventTypes.value])
const shownEvents = computed(() => events.value.filter((e) => !pick.value || e.event_type === pick.value).slice(0, 3))
</script>

<template>
  <div class="lt-home">
    <component :is="hero" />
    <section v-for="(key, i) in sections" :key="key" class="lt-sec" :class="[`lt-sec-${key}`, { 'lt-sec-alt': (layout.shell === 'atrium' || layout.alt) && i % 2 === 1, 'lt-sec-altr': layout.altR && i % 2 === 1 }]" :style="layout.altR && i % 2 === 1 ? { '--lt-altr': `${layout.altR}px` } : undefined">
      <div class="lt-cont">
        <SectionHead :n="i + 1" :title="meta(key).title" :sub="meta(key).sub" :link="meta(key).link" />
        <template v-if="key === 'events'">
          <div v-if="eventTypes.length" class="lt-e-pills lt-ref-pills"><button v-for="o in pills" :key="o.value" type="button" :aria-pressed="pick === o.value" @click="pick = o.value">{{ o.label }}</button></div>
          <EventsBlock :items="shownEvents" />
        </template>
        <HeritageBlock v-else-if="key === 'heritage'" />
        <GalleryBlock v-else-if="key === 'gallery'" :items="media" :count="6" />
        <NewsBlock v-else-if="key === 'news'" :items="news.slice(0, layout.news === 'cards' ? 4 : 3)" />
        <MembershipBlock v-else :items="tiers" :title="home.page_headings.membership?.title" />
      </div>
    </section>
    <section v-if="showQuote" class="lt-sec lt-sec-quote">
      <div class="lt-cont">
        <blockquote class="lt-quote">
          <p>&ldquo;{{ quote!.quote }}&rdquo;</p>
          <footer>{{ quote!.author_name }}<template v-if="quote!.author_context">, {{ quote!.author_context }}</template></footer>
        </blockquote>
        <LtQuoteNav />
      </div>
    </section>
    <SponsorsMarquee v-if="moduleEnabled('sponsors')" />
  </div>
</template>
