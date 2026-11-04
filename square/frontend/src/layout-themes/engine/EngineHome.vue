<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import SponsorsMarquee from '../../components/SponsorsMarquee.vue'
import { useLookup } from '../../composables/useLookup'
import { moduleEnabled } from '../../services/modules'
import { squareProfile } from '../../services/squareConfig'
import { formatEventDate } from '../../utils/date'
import { activeLayout } from '../layouts'
import { cta, cta2, dayMonth, eventsOn, galleryOn, newsOn, testimonialsOn } from '../useSiteLayout'
import { ensureHome, useSiteData } from '../useSiteData'
import EventsBlock from '../sections/EventsBlock.vue'
import GalleryBlock from '../sections/GalleryBlock.vue'
import NewsBlock from '../sections/NewsBlock.vue'
import LtButton from '../parts/LtButton.vue'
import LtHeadline from '../parts/LtHeadline.vue'
import LtLead from '../parts/LtLead.vue'
import LtPhoto from '../parts/LtPhoto.vue'
import LtQuoteNav from '../parts/LtQuoteNav.vue'

// The home page of an engine theme (W9-R10, design/tenant-themes-v7): five compositions, one per layout kit of the theme's first slot:
// K1 cards (hero band, programme cards, members and association band, news, gallery), K2 rows (hero with a big Up next card, numbers, photo strip,
// programme rows, quote, news and gallery side by side), K3 ledger (centred hero, Up next bar, big numbers, programme table, quote, three news
// columns, photo strip), K4 timeline (dark hero with an overlapping Up next card, numbers, programme timeline, quote, scrolling news, arched photos),
// K5 bento (one grid of tiles). Everything shown is the square's own; a part whose module is off is not there.
const layout = activeLayout!
const kit = layout.kit!
const { home, events, nextEvent, news, media, albumPics, quote, heroMain, aboutText } = useSiteData()
onMounted(ensureHome)
const { options: eventTypes } = useLookup('event_type')
const pick = ref('')
const pills = computed(() => [{ value: '', label: 'All events' }, ...eventTypes.value])
const prog = (n: number) => events.value.filter((e) => !pick.value || e.event_type === pick.value).slice(0, n)
const when = computed(() => (nextEvent.value ? dayMonth(nextEvent.value.start_datetime) : null))
const blurb = computed(() => home.value.blurb || aboutText.value.split(/\n\n/)[0] || '')
const hasQuote = computed(() => testimonialsOn && !!quote.value)
const eb = computed(() => home.value.eyebrow)
const photos = computed(() => media.value.slice(0, 6))
const ARCH = ['3/4', '1/1', '4/5', '1/1']
</script>

<template>
  <div class="lt-home lt-e-home" :class="`lt-kit-${kit}`">
    <!-- K1: cards -->
    <template v-if="kit === 'K1'">
      <section class="lt-e-band lt-e-sunk">
        <div class="lt-cont lt-e-two">
          <div class="lt-stack">
            <span v-if="eb" class="lt-e-eb">{{ eb }}</span>
            <LtHeadline />
            <LtLead />
            <div class="lt-ctas"><LtButton :to="cta.to">{{ cta.label }}</LtButton><LtButton :to="cta2.to" kind="o">{{ cta2.label }} →</LtButton></div>
            <div v-if="home.stats.length" class="lt-e-statrow"><div v-for="s in home.stats" :key="s.label"><b>{{ s.value }}</b><span>{{ s.label }}</span></div></div>
          </div>
          <div class="lt-e-stage">
            <LtPhoto :src="heroMain" alt="" ratio="5 / 4" class="lt-e-stagephoto" />
            <router-link v-if="eventsOn && nextEvent && when" :to="`/events/${nextEvent.slug}`" class="lt-e-floatcard">
              <span class="lt-e-dateblock"><b>{{ when.day }}</b><i>{{ when.month }}</i></span>
              <span class="lt-e-fc-main"><small>Up next</small><strong>{{ nextEvent.title }}</strong><span>{{ formatEventDate(nextEvent.start_datetime) }}<template v-if="nextEvent.venue"> · {{ nextEvent.venue }}</template></span></span>
              <span class="lt-e-fc-go">Programme →</span>
            </router-link>
            <div v-if="galleryOn && photos.length > 1" class="lt-e-thumbs"><LtPhoto v-for="m in photos.slice(1, 4)" :key="m.id" :src="m.thumbnail_url" alt="" ratio="1" /></div>
          </div>
        </div>
      </section>
      <section v-if="eventsOn" class="lt-e-band">
        <div class="lt-cont lt-e-col">
          <div class="lt-e-head"><div><span class="lt-e-eb">Programme</span><h2 class="lt-e-h">What's on this season</h2></div><LtButton to="/events" kind="o">View all</LtButton></div>
          <div class="lt-e-pills"><button v-for="o in pills" :key="o.value" type="button" :aria-pressed="pick === o.value" @click="pick = o.value">{{ o.label }}</button></div>
          <EventsBlock :items="prog(3)" variant="cards" />
        </div>
      </section>
      <section v-if="hasQuote || blurb" class="lt-e-band lt-e-inv">
        <div class="lt-cont lt-e-two">
          <div v-if="hasQuote" class="lt-stack"><span v-if="home.testimonials_eyebrow" class="lt-e-eb">{{ home.testimonials_eyebrow }}</span><blockquote class="lt-e-quote"><p>&ldquo;{{ quote!.quote }}&rdquo;</p><footer>{{ quote!.author_name }}<template v-if="quote!.author_context">, {{ quote!.author_context }}</template></footer></blockquote><LtQuoteNav /><LtButton v-if="moduleEnabled('testimonials') && home.testimonials_button" to="/testimonials" kind="ow">{{ home.testimonials_button }}</LtButton></div>
          <div v-if="blurb" class="lt-stack"><span v-if="home.association_eyebrow" class="lt-e-eb">{{ home.association_eyebrow }}</span><p class="lt-e-big">{{ blurb }}</p><LtButton v-if="home.association_button" to="/about" kind="w">{{ home.association_button }}</LtButton></div>
        </div>
      </section>
      <section v-if="newsOn" class="lt-e-band">
        <div class="lt-cont lt-e-col"><div class="lt-e-head"><h2 class="lt-e-h">News &amp; notices</h2><LtButton to="/news" kind="o">View all</LtButton></div><NewsBlock :items="news.slice(0, 3)" variant="cards" /></div>
      </section>
      <section v-if="galleryOn" class="lt-e-band lt-e-card">
        <div class="lt-cont lt-e-col lt-e-center"><span class="lt-e-eb">Gallery</span><h2 class="lt-e-h">Moments from {{ squareProfile.name }}</h2><GalleryBlock :items="albumPics" :count="3" variant="framed" /><LtButton to="/gallery" kind="o">View gallery</LtButton></div>
      </section>
    </template>

    <!-- K2: rows -->
    <template v-else-if="kit === 'K2'">
      <section class="lt-e-band lt-e-tight">
        <div class="lt-cont lt-e-two">
          <div class="lt-stack">
            <span v-if="eb" class="lt-e-eb">{{ eb }}</span>
            <LtHeadline />
            <LtLead />
            <div class="lt-ctas"><LtButton :to="cta.to">{{ cta.label }}</LtButton><LtButton :to="cta2.to" kind="o">{{ cta2.label }} →</LtButton></div>
          </div>
          <router-link v-if="eventsOn && nextEvent && when" :to="`/events/${nextEvent.slug}`" class="lt-e-nextbig">
            <small>Up next</small><span class="lt-e-bigdate"><b>{{ when.day }}</b><i>{{ when.month }}</i></span><strong>{{ nextEvent.title }}</strong><span class="lt-e-iv">{{ formatEventDate(nextEvent.start_datetime) }}<template v-if="nextEvent.venue"> · {{ nextEvent.venue }}</template></span><span class="lt-e-nextbtn">Event details →</span>
          </router-link>
        </div>
      </section>
      <div v-if="home.stats.length" class="lt-cont"><div class="lt-e-ruled"><div v-for="s in home.stats" :key="s.label"><b>{{ s.value }}</b><span>{{ s.label }}</span></div></div></div>
      <section v-if="galleryOn && photos.length > 3" class="lt-e-band lt-e-slim"><div class="lt-cont"><div class="lt-e-strip4"><LtPhoto v-for="(m, i) in photos.slice(0, 4)" :key="m.id" :src="m.thumbnail_url" alt="" :ratio="ARCH[i]" :class="{ 'lt-e-arch': i % 2 }" /></div></div></section>
      <section v-if="eventsOn" class="lt-e-band lt-e-card">
        <div class="lt-cont lt-e-side">
          <div class="lt-e-sticky"><span class="lt-e-eb">Programme</span><h2 class="lt-e-h">What's on this season</h2><div class="lt-e-pills"><button v-for="o in pills" :key="o.value" type="button" :aria-pressed="pick === o.value" @click="pick = o.value">{{ o.label }}</button></div><LtButton to="/events" kind="o">Full programme →</LtButton></div>
          <EventsBlock :items="prog(4)" variant="list" class="lt-e-ruletop" />
        </div>
      </section>
      <section v-if="hasQuote" class="lt-e-band lt-e-acc">
        <div class="lt-cont lt-e-center"><span v-if="home.testimonials_eyebrow" class="lt-e-eb lt-e-onacc">{{ home.testimonials_eyebrow }}</span><blockquote class="lt-e-quote lt-e-quote-xl"><p>&ldquo;{{ quote!.quote }}&rdquo;</p><footer>{{ quote!.author_name }}<template v-if="quote!.author_context">, {{ quote!.author_context }}</template></footer></blockquote><LtQuoteNav /><div class="lt-ctas lt-ctas-center"><LtButton v-if="moduleEnabled('testimonials') && home.testimonials_button" to="/testimonials" kind="ow">{{ home.testimonials_button }}</LtButton><LtButton v-if="home.association_button" to="/about" kind="w">{{ home.association_button }}</LtButton></div></div>
      </section>
      <section v-if="newsOn || galleryOn" class="lt-e-band">
        <div class="lt-cont lt-e-two2">
          <div v-if="newsOn"><div class="lt-e-head"><h2 class="lt-e-h lt-e-h-s">News &amp; notices</h2><router-link to="/news" class="lt-e-link">All news →</router-link></div><NewsBlock :items="news.slice(0, 4)" variant="index" class="lt-e-ruletop" /></div>
          <div v-if="galleryOn"><div class="lt-e-head"><h2 class="lt-e-h lt-e-h-s">From the gallery</h2><router-link to="/gallery" class="lt-e-link">Open gallery →</router-link></div><GalleryBlock :items="albumPics" :count="4" variant="uniform" /></div>
        </div>
      </section>
    </template>

    <!-- K3: ledger -->
    <template v-else-if="kit === 'K3'">
      <section class="lt-e-band lt-e-hero3">
        <div class="lt-cont lt-e-center lt-stack-c">
          <span v-if="eb" class="lt-e-eb">{{ eb }}</span>
          <LtHeadline />
          <LtLead />
          <div class="lt-ctas lt-ctas-center"><LtButton :to="cta.to">{{ cta.label }}</LtButton><LtButton :to="cta2.to" kind="o">{{ cta2.label }} →</LtButton></div>
        </div>
      </section>
      <router-link v-if="eventsOn && nextEvent && when" :to="`/events/${nextEvent.slug}`" class="lt-e-nextbar"><div class="lt-cont"><small>Up next</small><b>{{ when.day }} {{ when.month }}</b><strong>{{ nextEvent.title }}</strong><span>{{ nextEvent.venue }}</span><span>Details →</span></div></router-link>
      <section v-if="home.stats.length" class="lt-e-band lt-e-slim"><div class="lt-cont"><div class="lt-e-bignums"><div v-for="s in home.stats" :key="s.label"><b>{{ s.value }}</b><span>{{ s.label }}</span></div></div></div></section>
      <section v-if="eventsOn" class="lt-e-band lt-e-card">
        <div class="lt-cont lt-e-col">
          <div class="lt-e-head"><div><span class="lt-e-eb">Programme</span><h2 class="lt-e-h">This season</h2></div><div class="lt-e-pills"><button v-for="o in pills" :key="o.value" type="button" :aria-pressed="pick === o.value" @click="pick = o.value">{{ o.label }}</button></div></div>
          <EventsBlock :items="prog(5)" variant="table" />
          <LtButton to="/events" kind="o" class="lt-self-start">Full programme →</LtButton>
        </div>
      </section>
      <section v-if="hasQuote" class="lt-e-band">
        <div class="lt-cont lt-e-quote3"><span class="lt-e-bigq" aria-hidden="true">&ldquo;</span><div><span v-if="home.testimonials_eyebrow" class="lt-e-eb">{{ home.testimonials_eyebrow }}</span><blockquote class="lt-e-quote lt-e-quote-l"><p>{{ quote!.quote }}</p><footer>{{ quote!.author_name }}<template v-if="quote!.author_context">, {{ quote!.author_context }}</template></footer></blockquote><LtQuoteNav /><LtButton v-if="moduleEnabled('testimonials') && home.testimonials_button" to="/testimonials" kind="o">{{ home.testimonials_button }}</LtButton></div></div>
      </section>
      <section v-if="newsOn" class="lt-e-band lt-e-card"><div class="lt-cont lt-e-col"><div class="lt-e-head"><h2 class="lt-e-h lt-e-h-s">News &amp; notices</h2><router-link to="/news" class="lt-e-link">All news →</router-link></div><NewsBlock :items="news.slice(0, 3)" variant="cols" /></div></section>
      <section v-if="galleryOn" class="lt-e-band"><div class="lt-cont lt-e-col"><div class="lt-e-head"><h2 class="lt-e-h lt-e-h-s">Moments</h2><router-link to="/gallery" class="lt-e-link">Open gallery →</router-link></div><GalleryBlock :items="albumPics" :count="6" variant="grid" /></div></section>
    </template>

    <!-- K4: timeline -->
    <template v-else-if="kit === 'K4'">
      <section class="lt-e-hero4 lt-on-panel">
        <LtPhoto :src="heroMain" alt="" class="lt-e-hero4-bg" radius="0" />
        <div class="lt-cont lt-e-hero4-in">
          <div class="lt-stack">
            <span v-if="eb" class="lt-e-eb lt-e-onacc">{{ eb }}</span>
            <LtHeadline />
            <LtLead />
            <div class="lt-ctas"><LtButton :to="cta.to" kind="w">{{ cta.label }}</LtButton><LtButton :to="cta2.to" kind="ow">{{ cta2.label }} →</LtButton></div>
          </div>
        </div>
      </section>
      <div v-if="eventsOn && nextEvent && when" class="lt-cont"><router-link :to="`/events/${nextEvent.slug}`" class="lt-e-overlap"><span class="lt-e-dateblock"><b>{{ when.day }}</b><i>{{ when.month }}</i></span><span class="lt-e-fc-main"><small>Up next</small><strong>{{ nextEvent.title }}</strong><span>{{ formatEventDate(nextEvent.start_datetime) }}<template v-if="nextEvent.venue"> · {{ nextEvent.venue }}</template></span></span><span class="lt-btn lt-btn-p">Event details →</span></router-link></div>
      <section v-if="home.stats.length" class="lt-e-band lt-e-slim"><div class="lt-cont"><div class="lt-e-statrow lt-e-three"><div v-for="s in home.stats" :key="s.label"><b>{{ s.value }}</b><span>{{ s.label }}</span></div></div></div></section>
      <section v-if="eventsOn" class="lt-e-band lt-e-tight">
        <div class="lt-cont lt-e-col">
          <div class="lt-e-head"><div><span class="lt-e-eb">Programme</span><h2 class="lt-e-h">What's on this season</h2></div><div class="lt-e-pills"><button v-for="o in pills" :key="o.value" type="button" :aria-pressed="pick === o.value" @click="pick = o.value">{{ o.label }}</button></div></div>
          <EventsBlock :items="prog(4)" variant="agenda" />
          <LtButton to="/events" kind="o" class="lt-self-start">Full programme →</LtButton>
        </div>
      </section>
      <section v-if="hasQuote" class="lt-e-band lt-e-hl">
        <div class="lt-cont lt-e-center"><span v-if="home.testimonials_eyebrow" class="lt-e-eb">{{ home.testimonials_eyebrow }}</span><blockquote class="lt-e-quote lt-e-quote-l"><p>&ldquo;{{ quote!.quote }}&rdquo;</p><footer>{{ quote!.author_name }}<template v-if="quote!.author_context">, {{ quote!.author_context }}</template></footer></blockquote><LtQuoteNav /><LtButton v-if="moduleEnabled('testimonials') && home.testimonials_button" to="/testimonials" kind="o">{{ home.testimonials_button }}</LtButton></div>
      </section>
      <section v-if="newsOn" class="lt-e-band lt-e-tight"><div class="lt-cont lt-e-col"><div class="lt-e-head"><h2 class="lt-e-h lt-e-h-s">News &amp; notices</h2><router-link to="/news" class="lt-e-link">All news →</router-link></div><div class="lt-e-hscroll"><NewsBlock :items="news.slice(0, 6)" variant="cards" /></div></div></section>
      <section v-if="galleryOn" class="lt-e-band lt-e-card"><div class="lt-cont lt-e-col"><div class="lt-e-head"><h2 class="lt-e-h lt-e-h-s">Moments from {{ squareProfile.name }}</h2><router-link to="/gallery" class="lt-e-link">Open gallery →</router-link></div><div class="lt-e-archs"><router-link v-for="a in albumPics.slice(0, 3)" :key="a.id" :to="`/gallery/${a.album_id}`"><LtPhoto :src="a.thumbnail_url" :alt="a.caption ?? ''" ratio="3 / 4" class="lt-e-archp" /><span>{{ a.caption }}</span></router-link></div></div></section>
    </template>

    <!-- K5: bento -->
    <template v-else>
      <section class="lt-e-band lt-e-tight">
        <div class="lt-cont">
          <div class="lt-bento">
            <div class="lt-tile5 lt-t-hl lt-t8 lt-stack">
              <span v-if="eb" class="lt-e-eb">{{ eb }}</span>
              <LtHeadline />
              <LtLead />
              <div class="lt-ctas"><LtButton :to="cta.to">{{ cta.label }}</LtButton><LtButton :to="cta2.to" kind="o">{{ cta2.label }} →</LtButton></div>
            </div>
            <router-link v-if="eventsOn && nextEvent && when" :to="`/events/${nextEvent.slug}`" class="lt-tile5 lt-t-inv lt-t4"><small>Up next</small><span class="lt-e-bigdate"><b>{{ when.day }}</b><i>{{ when.month }}</i></span><strong>{{ nextEvent.title }}</strong><span class="lt-e-iv">{{ nextEvent.venue }}</span></router-link>
            <div v-for="(s, i) in home.stats.slice(0, 3)" :key="s.label" class="lt-tile5 lt-t4" :class="i === 1 ? 'lt-t-sunk' : 'lt-t-card'"><b class="lt-e-stat5">{{ s.value }}</b><span class="lt-e-statl">{{ s.label }}</span></div>
            <div v-if="eventsOn" class="lt-tile5 lt-t-card lt-t7">
              <div class="lt-e-head"><h2 class="lt-e-h lt-e-h-s">This season</h2><div class="lt-e-pills"><button v-for="o in pills" :key="o.value" type="button" :aria-pressed="pick === o.value" @click="pick = o.value">{{ o.label }}</button></div></div>
              <EventsBlock :items="prog(3)" variant="list" />
              <router-link to="/events" class="lt-e-link">Full programme →</router-link>
            </div>
            <div v-if="hasQuote" class="lt-tile5 lt-t-acc lt-t5"><span v-if="home.testimonials_eyebrow" class="lt-e-eb lt-e-onacc">{{ home.testimonials_eyebrow }}</span><blockquote class="lt-e-quote"><p>&ldquo;{{ quote!.quote }}&rdquo;</p><footer>{{ quote!.author_name }}<template v-if="quote!.author_context">, {{ quote!.author_context }}</template></footer></blockquote><LtQuoteNav /><LtButton v-if="moduleEnabled('testimonials') && home.testimonials_button" to="/testimonials" kind="w">{{ home.testimonials_button }}</LtButton></div>
            <div v-if="newsOn" class="lt-tile5 lt-t-sunk lt-t6"><div class="lt-e-head"><h2 class="lt-e-h lt-e-h-s">News &amp; notices</h2><router-link to="/news" class="lt-e-link">All →</router-link></div><NewsBlock :items="news.slice(0, 3)" variant="index" /></div>
            <div v-if="galleryOn" class="lt-tile5 lt-t-card lt-t6"><div class="lt-e-head"><h2 class="lt-e-h lt-e-h-s">Gallery</h2><router-link to="/gallery" class="lt-e-link">Open →</router-link></div><GalleryBlock :items="albumPics" :count="4" variant="uniform" /></div>
            <div class="lt-tile5 lt-t-hl lt-t12 lt-e-cta"><div><h2 class="lt-e-h">Part of the community?</h2><p class="lt-lead">Join {{ squareProfile.name }} and keep it going.</p></div><div class="lt-ctas"><LtButton :to="cta.to">{{ cta.label }}</LtButton><LtButton v-if="home.association_button" to="/about" kind="o">{{ home.association_button }}</LtButton></div></div>
          </div>
        </div>
      </section>
    </template>

    <SponsorsMarquee v-if="moduleEnabled('sponsors')" />
  </div>
</template>
