<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import SponsorsMarquee from '../../components/SponsorsMarquee.vue'
import { useLookup } from '../../composables/useLookup'
import { moduleEnabled } from '../../services/modules'
import { formatEventDate } from '../../utils/date'
import { cta, cta2, eventsOn, galleryOn, newsOn, testimonialsOn } from '../useSiteLayout'
import { ensureHome, useSiteData } from '../useSiteData'
import EventsBlock from '../sections/EventsBlock.vue'
import HeritageBlock from '../sections/HeritageBlock.vue'
import MembershipBlock from '../sections/MembershipBlock.vue'
import NewsBlock from '../sections/NewsBlock.vue'
import LtButton from '../parts/LtButton.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtQuoteNav from '../parts/LtQuoteNav.vue'

// The home page of Japandi Atelier (W10-R3, design/tenant-themes-v7 'Japandi Atelier'): a split hero whose right side is a ledger of the next events
// in the palette's six swatches, the numbers under a rule, the programme as dated rows, the story as a centred timeline, an arched photo collage,
// the news as an index, the plans as rows and the sponsors. Everything shown is the square's own; a part whose module is off is not there.
const { home, events, news, albumPics, media, tiers, quote, aboutText } = useSiteData()
onMounted(ensureHome)
const { options: eventTypes } = useLookup('event_type')
const pick = ref('')
const pills = computed(() => [{ value: '', label: 'All events' }, ...eventTypes.value])
const prog = computed(() => events.value.filter((e) => !pick.value || e.event_type === pick.value).slice(0, 5))
const ledger = computed(() => events.value.slice(0, 6))
const eb = computed(() => home.value.eyebrow)
const hasStory = computed(() => !!(home.value.about_page.timeline.length || aboutText.value.trim() || home.value.blurb.trim()))
const hasQuote = computed(() => testimonialsOn && !!quote.value)
const strip = computed(() => (galleryOn ? media.value.slice(0, 3) : []))
const blurb = computed(() => home.value.blurb || '')
const pics = computed(() => albumPics.value.slice(0, 4))
const heading = (key: 'events' | 'heritage' | 'gallery' | 'news' | 'membership', fallback: string) => home.value.page_headings[key]?.title || fallback
</script>

<template>
  <div class="lt-home lt-jp">
    <section class="lt-jp-band lt-jp-hero">
      <div class="lt-cont lt-jp-two">
        <div class="lt-jp-copy">
          <span v-if="eb" class="lt-jp-eb">{{ eb }}</span>
          <LtHeadline />
          <LtLead />
          <div class="lt-ctas"><LtButton :to="cta.to">{{ cta.label }}</LtButton><LtButton :to="cta2.to" kind="o">{{ cta2.label }} →</LtButton></div>
        </div>
        <div v-if="eventsOn && ledger.length" class="lt-jp-ledger">
          <router-link v-for="(e, i) in ledger" :key="e.id" :to="`/events/${e.slug}`" class="lt-jp-lrow" :style="{ background: `var(--lt-sw${i % 6})`, color: `var(--lt-sw${i % 6}-fg)` }">
            <span class="lt-jp-lno">{{ String(i + 1).padStart(2, '0') }}</span>
            <span><strong>{{ e.title }}</strong><small>{{ formatEventDate(e.start_datetime) }}<template v-if="e.venue"> · {{ e.venue }}</template></small></span>
          </router-link>
        </div>
      </div>
    </section>

    <div v-if="strip.length === 3" class="lt-cont"><div class="lt-jp-strip"><router-link v-for="m in strip" :key="m.id" :to="`/gallery/${m.album_id}`"><LtPhoto :src="m.thumbnail_url" :alt="m.caption || m.album_title" ratio="4 / 5" radius="999px 999px 12px 12px" /></router-link></div></div>

    <div v-if="home.stats.length" class="lt-cont"><div class="lt-jp-stats"><div v-for="s in home.stats" :key="s.label"><b>{{ s.value }}</b><span>{{ s.label }}</span></div></div></div>

    <section v-if="eventsOn" class="lt-jp-band">
      <div class="lt-cont">
        <div class="lt-jp-head"><h2>{{ heading('events', 'Programme for the season') }}</h2><router-link to="/events">All events →</router-link></div>
        <div class="lt-jp-pills"><button v-for="o in pills" :key="o.value" type="button" :aria-pressed="pick === o.value" @click="pick = o.value">{{ o.label }}</button></div>
        <EventsBlock :items="prog" variant="list" chips />
      </div>
    </section>

    <section v-if="hasStory" class="lt-jp-band lt-jp-card">
      <div class="lt-cont">
        <div class="lt-jp-head"><h2>{{ heading('heritage', 'Where we come from') }}</h2><router-link to="/about">Our story →</router-link></div>
        <HeritageBlock variant="stack" />
        <div v-if="hasQuote" class="lt-jp-quote">
          <span v-if="home.testimonials_eyebrow" class="lt-jp-eb">{{ home.testimonials_eyebrow }}</span>
          <blockquote><p>&ldquo;{{ quote!.quote }}&rdquo;</p><footer>{{ quote!.author_name }}<template v-if="quote!.author_context">, {{ quote!.author_context }}</template></footer></blockquote>
          <div class="lt-jp-qnav">
            <LtQuoteNav />
            <LtButton v-if="moduleEnabled('testimonials') && home.testimonials_button" to="/testimonials" kind="o">{{ home.testimonials_button }}</LtButton>
          </div>
        </div>
        <div v-else-if="testimonialsOn && home.testimonials_empty_text" class="lt-jp-quote">
          <span v-if="home.testimonials_eyebrow" class="lt-jp-eb">{{ home.testimonials_eyebrow }}</span>
          <p class="lt-jp-lead">{{ home.testimonials_empty_text }}</p>
          <LtButton v-if="home.testimonials_button" to="/testimonials" kind="o">{{ home.testimonials_button }}</LtButton>
        </div>
        <div v-if="blurb || home.association_eyebrow || home.association_button" class="lt-jp-quote lt-jp-assoc">
          <span v-if="home.association_eyebrow" class="lt-jp-eb">{{ home.association_eyebrow }}</span>
          <p v-if="blurb" class="lt-jp-lead">{{ blurb }}</p>
          <LtButton v-if="home.association_button" to="/about" kind="o">{{ home.association_button }}</LtButton>
        </div>
      </div>
    </section>

    <section v-if="galleryOn && pics.length" class="lt-jp-band">
      <div class="lt-cont">
        <div class="lt-jp-head"><h2>{{ heading('gallery', 'Moments from the archive') }}</h2><router-link to="/gallery">Open gallery →</router-link></div>
        <div class="lt-jp-collage">
          <router-link :to="`/gallery/${pics[0]!.album_id}`" class="lt-jp-arch"><LtPhoto :src="pics[0]!.thumbnail_url" :alt="pics[0]!.caption ?? ''" ratio="1" radius="999px 999px 12px 12px" /><span v-if="pics[0]!.caption" class="lt-jp-cap">{{ pics[0]!.caption }}</span></router-link>
          <div class="lt-jp-side"><router-link v-for="p in pics.slice(1)" :key="p.id" :to="`/gallery/${p.album_id}`"><LtPhoto :src="p.thumbnail_url" :alt="p.caption ?? ''" ratio="16 / 10" radius="12px" /><span v-if="p.caption" class="lt-jp-cap">{{ p.caption }}</span></router-link></div>
        </div>
      </div>
    </section>

    <section v-if="newsOn && news.length" class="lt-jp-band lt-jp-card">
      <div class="lt-cont">
        <div class="lt-jp-head"><h2>{{ heading('news', 'Notices and announcements') }}</h2><router-link to="/news">All news →</router-link></div>
        <div class="lt-jp-narrow"><NewsBlock :items="news.slice(0, 3)" variant="index" /></div>
      </div>
    </section>

    <section v-if="tiers.length" class="lt-jp-band">
      <div class="lt-cont">
        <div class="lt-jp-head"><h2>{{ heading('membership', 'Plans for every household') }}</h2></div>
        <div class="lt-jp-narrow lt-jp-wide"><MembershipBlock :items="tiers" :title="home.page_headings.membership?.title" variant="rows" /></div>
      </div>
    </section>

    <SponsorsMarquee v-if="moduleEnabled('sponsors')" />
  </div>
</template>
