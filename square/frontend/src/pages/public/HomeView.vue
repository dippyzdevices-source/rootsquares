<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { moduleEnabled, offeredPhrase } from '../../services/modules'
import SponsorsMarquee from '../../components/SponsorsMarquee.vue'
import { fetchEvents, type EventSummary } from '../../services/eventsApi'
import { EMPTY_HOME_CONTENT, loadHomeContent } from '../../services/siteContent'
import { fetchAlbums, fetchGalleryMedia, type AlbumSummary, type GalleryMediaItem } from '../../services/galleryApi'
import { fetchNews, type NewsSummary } from '../../services/newsApi'
import { fetchTestimonials, type Testimonial } from '../../services/testimonialsApi'
import { formatDateTime, formatEventDate } from '../../utils/date'
import { ensureMinLoadingDuration } from '../../utils/minLoadingDuration'
import { useLookup } from '../../composables/useLookup'

const home = ref({ ...EMPTY_HOME_CONTENT }) // the square's own words (W6-R64); empty keys show neutral text
const upcomingEvents = ref<EventSummary[]>([])
const eventsLoading = ref(true)
const eventsError = ref(false)
// Separate from upcomingEvents (which drives the hero's "Up next" card and must always show
// the true next event) — this is the "What's on this season" grid, which the Programme filter
// below re-fetches independently so filtering it never changes what the hero shows.
const programmeEvents = ref<EventSummary[]>([])
const programmeLoading = ref(true)
const programmeError = ref(false)
const programmeFilter = ref('')
// Same real event_type taxonomy as EventsListView.vue's typeOptions — not the design system
// mockup's fictional "Music/Food/Children" categories, which don't correspond to real data.
const { options: eventTypes, label: eventTypeLabel } = useLookup('event_type')
const { label: newsCategoryLabel } = useLookup('news_category')
const programmeTypeOptions = computed(() => [{ value: '', label: 'All events' }, ...eventTypes.value])
// Bottom "Moments from {{ squareProfile.name }}" preview always shows just the 3 most recent albums.
const galleryPreviewAlbums = ref<AlbumSummary[]>([])
const newsItems = ref<NewsSummary[]>([])
const membershipsOn = moduleEnabled('memberships') // W8-R19: no Become a member button without the Memberships module
const eventsOn = moduleEnabled('events') // W8-R28: a square without the Events module has no programme, no Up next card and no request for events
const galleryOn = moduleEnabled('gallery') // W8-R17: a square without the Gallery module has no gallery part and no photo carousel
const newsOn = moduleEnabled('news') // W8-R16: a square without the News module has no news part
const defaultIntro = offeredPhrase() ? `${offeredPhrase().charAt(0).toUpperCase()}${offeredPhrase().slice(1)}, all in one place.` : ''
const testimonialsOn = moduleEnabled('testimonials') // W8-R10: a square without the Testimonials module has no testimonial part
const testimonials = ref<Testimonial[]>([])
const testimonialIndex = ref(0)
let testimonialTimer: ReturnType<typeof setInterval> | null = null
// The "upcoming" fetch already orders by start_datetime ascending (soonest first, see
// app/events/routes.py), so the first item IS the next event — no separate fetch needed.
const featuredEvent = computed(() => upcomingEvents.value[0] ?? null)
const featuredEventDay = computed(() =>
  featuredEvent.value ? new Date(featuredEvent.value.start_datetime).getDate().toString() : '',
)
const featuredEventMonth = computed(() =>
  featuredEvent.value
    ? new Date(featuredEvent.value.start_datetime).toLocaleDateString('en-GB', { month: 'short' })
    : '',
)
// [0] is the HeroStage primary photo, [1]-[3] the secondary/tertiary/quaternary strip
// thumbnails underneath. Drawn from a flat pool of individual photos across every published
// album (GET /api/gallery/media) — not one arbitrary "cover" (album.media[0]) per album — so
// which photo is a "cover" is irrelevant here and the strip shows whenever there are 4+ real
// photos anywhere in the gallery, regardless of how many albums they're spread across. All 4
// re-shuffle together as a set on each carousel tick (below) — same pattern as
// EventDetailView.vue's banner autoplay: paused while a real mouse hovers the hero
// (WCAG 2.2.2), skipped entirely under prefers-reduced-motion.
const heroPhotoPool = ref<GalleryMediaItem[]>([])
const heroPhotos = ref<GalleryMediaItem[]>([])
const HERO_PHOTO_INTERVAL_MS = 3000
const heroPhotosPausedByHover = ref(false)
let heroPhotoTimer: ReturnType<typeof setInterval> | null = null

function pickRandomHeroPhotos(pool: GalleryMediaItem[]): GalleryMediaItem[] {
  const shuffled = [...pool].sort(() => Math.random() - 0.5)
  return shuffled.slice(0, 4)
}

function stopHeroPhotoCarousel() {
  if (heroPhotoTimer !== null) {
    clearInterval(heroPhotoTimer)
    heroPhotoTimer = null
  }
}

function startHeroPhotoCarousel() {
  stopHeroPhotoCarousel()
  if (heroPhotoPool.value.length === 0 || heroPhotosPausedByHover.value) return
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches) return
  heroPhotoTimer = setInterval(() => {
    heroPhotos.value = pickRandomHeroPhotos(heroPhotoPool.value)
  }, HERO_PHOTO_INTERVAL_MS)
}

function pauseHeroPhotoCarouselOnHover() {
  // See EventDetailView.vue's pauseAutoplayOnHover — mobile fires a synthetic mouseenter on
  // tap with no matching mouseleave, so only a real mouse (hover: hover) pauses this.
  if (!window.matchMedia?.('(hover: hover)')?.matches) return
  heroPhotosPausedByHover.value = true
  stopHeroPhotoCarousel()
}

function resumeHeroPhotoCarouselAfterHover() {
  heroPhotosPausedByHover.value = false
  startHeroPhotoCarousel()
}
const currentTestimonial = computed(() => testimonials.value[testimonialIndex.value] ?? null)

function showNextTestimonial() {
  if (!testimonials.value.length) return
  testimonialIndex.value = (testimonialIndex.value + 1) % testimonials.value.length
}

function showPreviousTestimonial() {
  if (!testimonials.value.length) return
  testimonialIndex.value = (testimonialIndex.value - 1 + testimonials.value.length) % testimonials.value.length
}

function startTestimonialAutoAdvance() {
  stopTestimonialAutoAdvance()
  if (testimonials.value.length > 1) {
    testimonialTimer = setInterval(showNextTestimonial, 7000)
  }
}

function stopTestimonialAutoAdvance() {
  if (testimonialTimer) {
    clearInterval(testimonialTimer)
    testimonialTimer = null
  }
}

onUnmounted(() => {
  stopTestimonialAutoAdvance()
  stopHeroPhotoCarousel()
})

async function loadProgrammeEvents() {
  programmeLoading.value = true
  programmeError.value = false
  try {
    const data = await fetchEvents({ when: 'upcoming', type: programmeFilter.value || undefined, perPage: 3 })
    programmeEvents.value = data.items
  } catch {
    programmeError.value = true
  } finally {
    programmeLoading.value = false
  }
}

watch(programmeFilter, loadProgrammeEvents)

onMounted(async () => {
  void loadHomeContent().then((content) => (home.value = content))
  const startedAt = Date.now()
  try {
    if (!eventsOn) throw new Error('no Events module')
    const data = await fetchEvents({ when: 'upcoming', perPage: 3 })
    upcomingEvents.value = data.items
    programmeEvents.value = data.items
  } catch {
    eventsError.value = eventsOn
    programmeError.value = eventsOn
  } finally {
    if (eventsOn) await ensureMinLoadingDuration(startedAt)
    eventsLoading.value = false
    programmeLoading.value = false
  }

  try {
    if (!galleryOn) throw new Error('no Gallery module')
    const albumsData = await fetchAlbums(1, 3)
    galleryPreviewAlbums.value = albumsData.items
  } catch {
    // Gallery preview is non-critical; leave it empty on failure rather than erroring the page.
  }

  try {
    if (!galleryOn) throw new Error('no Gallery module')
    heroPhotoPool.value = await fetchGalleryMedia(40, true)
    heroPhotos.value = pickRandomHeroPhotos(heroPhotoPool.value)
    startHeroPhotoCarousel()
  } catch {
    // Hero photo carousel is non-critical; leave it on the placeholder state on failure.
  }

  try {
    if (!newsOn) throw new Error('no News module')
    const newsData = await fetchNews({ page: 1, perPage: 3 })
    newsItems.value = newsData.items
  } catch {
    // News preview is non-critical; leave it empty on failure rather than erroring the page.
  }

  if (!testimonialsOn) return
  try {
    const testimonialsData = await fetchTestimonials()
    testimonials.value = testimonialsData.items
    startTestimonialAutoAdvance()
  } catch {
    // Testimonials are non-critical; leave the section hidden on failure.
  }
})
</script>

<template>
  <div class="ds-scope">
    <!-- Hero -->
    <section class="ds-band ds-band-wash">
      <div class="ds-container ds-row ds-row--split">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ home.eyebrow || 'Welcome' }}</span>
          <span v-if="home.script_line" class="ds-script">{{ home.script_line }}</span>
          <h1 class="ds-display ds-display-l">{{ home.headline || squareProfile.name }}</h1>
          <p v-if="home.local_line" class="ds-bn" style="font-size: var(--ds-text-subtitle); color: var(--ds-text-muted)">{{ home.local_line }}</p>
          <p class="ds-intro">
            {{ home.intro || defaultIntro }}
            <span v-if="home.intro_name" style="display: block; margin-top: var(--ds-space-3); font-family: var(--ds-font-script); font-style: normal; font-size: var(--ds-text-display-m); font-weight: 400; color: var(--ds-terracotta-500)">{{ home.intro_name }}</span>
            <template v-if="home.intro_suffix">{{ home.intro_suffix }}</template>
          </p>
          <div style="display: flex; gap: var(--ds-space-3); margin-top: var(--ds-space-6); flex-wrap: wrap">
            <BaseButton v-if="membershipsOn" to="/membership" size="lg">Become a member</BaseButton>
            <BaseButton v-if="eventsOn" to="/events" variant="secondary" size="lg">
              See the programme
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
            </BaseButton>
          </div>
          <div v-if="home.stats.length" style="display: flex; gap: var(--ds-space-6); margin-top: var(--ds-space-7); flex-wrap: wrap">
            <div v-for="stat in home.stats" :key="stat.label">
              <div style="font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); color: var(--ds-text-heading)">{{ stat.value }}</div>
              <div class="ds-eyebrow" style="color: var(--ds-text-muted)">{{ stat.label }}</div>
            </div>
          </div>
        </div>

        <!-- The photo frame is the Gallery module's (W8-R17); the "Up next" card under it is the Events module's and stays without a photo. -->
        <div v-if="galleryOn || featuredEvent" style="max-width: 480px; margin-left: auto; width: 100%" @mouseenter="pauseHeroPhotoCarouselOnHover" @mouseleave="resumeHeroPhotoCarouselAfterHover">
          <div style="position: relative">
            <div v-if="galleryOn" class="ds-hero-stage-shot" style="aspect-ratio: 5 / 4">
              <img v-if="heroPhotos[0]" :src="heroPhotos[0].thumbnail_url" :alt="heroPhotos[0].caption || heroPhotos[0].album_title" />
              <div v-else class="ds-placeholder" style="width: 100%; height: 100%"><span class="ds-placeholder-glyph">✺</span></div>
            </div>
            <router-link v-if="featuredEvent" :to="`/events/${featuredEvent.slug}`" class="ds-hero-stage-ribbon" :style="galleryOn ? undefined : { marginTop: 0 }">
              <div class="ds-hero-stage-ribbon-date">
                <div class="ds-hero-stage-ribbon-day">{{ featuredEventDay }}</div>
                <div class="ds-eyebrow" style="font-size: 10px; color: var(--ds-text-muted)">{{ featuredEventMonth }}</div>
              </div>
              <div class="ds-hero-stage-ribbon-info">
                <div class="ds-eyebrow" style="font-size: 10px">Up next</div>
                <div class="ds-hero-stage-ribbon-title">{{ featuredEvent.title }}</div>
                <div class="ds-hero-stage-ribbon-meta">{{ formatEventDate(featuredEvent.start_datetime) }}<span v-if="featuredEvent.venue"> · {{ featuredEvent.venue }}</span></div>
              </div>
              <span class="ds-hero-stage-ribbon-link">Programme →</span>
            </router-link>
          </div>

          <div v-if="heroPhotos.length > 3" class="ds-hero-stage-strip">
            <div v-for="photo in heroPhotos.slice(1)" :key="photo.id" class="ds-hero-stage-shot" style="aspect-ratio: 1 / 1">
              <img :src="photo.thumbnail_url" :alt="photo.caption || photo.album_title" />
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Programme -->
    <section v-if="eventsOn" class="ds-band ds-band-paper">
      <div class="ds-container" style="display: flex; flex-direction: column; gap: var(--ds-space-7)">
        <div style="display: flex; justify-content: space-between; align-items: flex-end; gap: var(--ds-space-6); flex-wrap: wrap">
          <div class="ds-heading">
            <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Programme</span>
            <h2 class="ds-display ds-display-s">What's on this season</h2>
          </div>
          <BaseButton to="/events" variant="paper" size="sm">View all</BaseButton>
        </div>

        <div style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
          <button
            v-for="opt in programmeTypeOptions"
            :key="opt.value"
            type="button"
            class="ds-tag"
            :class="{ 'ds-tag-selected': programmeFilter === opt.value }"
            @click="programmeFilter = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>

        <BaseLoadingState v-if="programmeLoading" label="Loading upcoming events…" />
        <BaseEmptyState v-else-if="programmeError" title="Couldn't load events" description="Please try again shortly." />
        <BaseEmptyState v-else-if="programmeEvents.length === 0" title="No upcoming events" description="Check back soon for new events." />
        <div v-else class="ds-cards ds-cards--3">
          <router-link v-for="event in programmeEvents" :key="event.id" :to="`/events/${event.slug}`" class="ds-event-card" :class="{ 'ds-event-card-draft': !event.published }">
            <div class="ds-event-media" :class="{ 'ds-placeholder': !event.banner_image }">
              <img v-if="event.banner_image" :src="event.banner_image" :alt="event.title" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover" />
              <span class="ds-badge ds-badge-accent" style="position: relative">{{ eventTypeLabel(event.event_type) }}</span>
              <span v-if="!event.published" class="ds-badge ds-badge-neutral" style="position: relative">Draft</span>
              <span v-else-if="event.sales_closed" class="ds-badge ds-badge-neutral sales-closed-pill" style="position: relative">Sales closed</span>
              <span v-else-if="event.sales_not_open && event.sales_open_at" class="ds-badge ds-badge-accent sales-not-open-pill" style="position: relative; gap: 4px"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg>Tickets open {{ formatDateTime(event.sales_open_at) }}</span>
            </div>
            <div class="ds-event-body">
              <p class="ds-meta">{{ formatEventDate(event.start_datetime) }}</p>
              <h3 class="ds-event-title">{{ event.title }}</h3>
              <p v-if="event.venue" class="ds-meta">{{ event.venue }}</p>
              <p v-if="event.short_description" class="ds-body ds-desc-s" :data-desc-style="event.description_style ?? undefined">{{ event.short_description }}</p>
              <span class="ds-event-cta">Details →</span>
            </div>
          </router-link>
        </div>
      </div>
    </section>

    <!-- Association / testimonial -->
    <section class="ds-band ds-band-hero">
      <div class="ds-container ds-row ds-row--half">
        <div v-if="testimonialsOn && currentTestimonial">
          <span v-if="home.testimonials_eyebrow" class="ds-eyebrow" style="color: var(--ds-saffron-300)">{{ home.testimonials_eyebrow }}</span>
          <span v-if="currentTestimonial.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span>
          <blockquote class="ds-pullquote ds-pullquote-onDark" style="margin-top: var(--ds-space-4)">
            <p>&ldquo;{{ currentTestimonial.quote }}&rdquo;</p>
            <footer>
              <span class="ds-quote-rule" />
              {{ currentTestimonial.author_name }}<template v-if="currentTestimonial.author_context">, {{ currentTestimonial.author_context }}</template>
            </footer>
          </blockquote>
          <div v-if="testimonials.length > 1" class="ds-testimonial-nav">
            <button type="button" class="ds-icon-btn ds-icon-btn-onDark" aria-label="Previous testimonial" title="Previous testimonial" @click="showPreviousTestimonial">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
            </button>
            <div class="ds-testimonial-dots">
              <button
                v-for="(item, dotIndex) in testimonials"
                :key="item.id"
                type="button"
                class="ds-testimonial-dot ds-testimonial-dot-onDark"
                :class="{ 'ds-testimonial-dot-active': dotIndex === testimonialIndex }"
                :aria-label="`Go to testimonial ${dotIndex + 1}`"
                @click="testimonialIndex = dotIndex"
              />
            </div>
            <button type="button" class="ds-icon-btn ds-icon-btn-onDark" aria-label="Next testimonial" title="Next testimonial" @click="showNextTestimonial">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
            </button>
          </div>
          <BaseButton v-if="home.testimonials_button" to="/testimonials" variant="accent-outline" style="margin-top: var(--ds-space-5)">{{ home.testimonials_button }}</BaseButton>
        </div>
        <div v-else-if="testimonialsOn && home.testimonials_empty_text">
          <span v-if="home.testimonials_eyebrow" class="ds-eyebrow" style="color: var(--ds-saffron-300)">{{ home.testimonials_eyebrow }}</span>
          <p class="ds-body-l" style="color: var(--ds-paper-200); margin-top: var(--ds-space-4)">{{ home.testimonials_empty_text }}</p>
          <BaseButton v-if="home.testimonials_button" to="/testimonials" variant="accent-outline" style="margin-top: var(--ds-space-5)">{{ home.testimonials_button }}</BaseButton>
        </div>
        <div>
          <span v-if="home.association_eyebrow" class="ds-eyebrow" style="color: var(--ds-saffron-300)">{{ home.association_eyebrow }}</span>
          <p class="ds-body-l" style="color: var(--ds-paper-200); margin-top: var(--ds-space-4)">
            {{ home.blurb || `${squareProfile.name} is run entirely by volunteers, for the community.` }}
          </p>
          <BaseButton v-if="home.association_button" to="/about" variant="inverse" style="margin-top: var(--ds-space-5)">{{ home.association_button }}</BaseButton>
        </div>
      </div>
    </section>

    <!-- News -->
    <section v-if="newsOn" class="ds-band ds-band-paper">
      <div class="ds-container" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
        <div style="display: flex; align-items: baseline; justify-content: space-between">
          <h2 class="ds-title">News &amp; notices</h2>
          <BaseButton to="/news" variant="paper" size="sm">View all</BaseButton>
        </div>
        <BaseEmptyState v-if="newsItems.length === 0" title="No news yet" description="Check back soon for updates." />
        <!-- Same card as the /news page's grid, three across so the row is symmetric. -->
        <div v-else class="ds-cards ds-cards--3">
          <router-link v-for="article in newsItems" :key="article.id" :to="`/news/${article.slug}`" class="ds-card ds-card-interactive" style="padding: 0; overflow: hidden; display: flex; flex-direction: column">
            <div style="aspect-ratio: 16 / 9; background: var(--ds-surface-sunken); background-image: var(--ds-grain); display: flex; align-items: center; justify-content: center">
              <img v-if="article.banner_image" :src="article.banner_image" :alt="article.title" style="width: 100%; height: 100%; object-fit: cover" />
              <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--ds-text-faint)"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2" /><path d="M18 14h-8" /><path d="M15 18h-5" /><path d="M10 6h8v4h-8V6Z" /></svg>
            </div>
            <div style="padding: var(--ds-space-4) var(--ds-space-5) var(--ds-space-5); display: flex; flex-direction: column; gap: var(--ds-space-3); flex: 1">
              <div style="display: flex; align-items: center; gap: var(--ds-space-3)">
                <span v-if="article.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span>
                <span v-if="article.category" class="ds-badge ds-badge-neutral">{{ newsCategoryLabel(article.category) }}</span>
                <span v-if="article.published_at" class="ds-caption">{{ formatEventDate(article.published_at) }}</span>
              </div>
              <h3 class="ds-card-title" style="margin-top: 0">{{ article.title }}</h3>
              <p v-if="article.summary" class="ds-meta ds-desc-s" :data-desc-style="article.description_style ?? undefined">{{ article.summary }}</p>
              <p class="ds-caption" style="margin-top: auto; padding-top: var(--ds-space-2)">
                <template v-if="article.author">{{ article.author }} · </template>{{ article.read_minutes }} min read
              </p>
            </div>
          </router-link>
        </div>
      </div>
    </section>

    <!-- Gallery -->
    <section v-if="galleryOn" class="ds-band ds-band-card">
      <div class="ds-container">
        <div class="ds-heading ds-heading--center">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Gallery</span>
          <h2 class="ds-display ds-display-s">Moments from {{ squareProfile.name }}</h2>
          <p class="ds-intro" style="margin-left: auto; margin-right: auto">Photos from our festivals and gatherings, shared by the community.</p>
        </div>
        <div class="ds-motif" style="margin: var(--ds-space-6) auto">
          <span></span><span class="ds-motif-glyph">❖</span><span></span>
        </div>
        <BaseEmptyState v-if="galleryPreviewAlbums.length === 0" title="No photos yet" description="Check back after the next event." />
        <div v-else class="ds-gallery-grid" style="grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr))">
          <router-link v-for="album in galleryPreviewAlbums" :key="album.id" :to="`/gallery/${album.id}`" class="ds-gallery-item">
            <div class="ds-rect" style="aspect-ratio: 4 / 3">
              <img v-if="album.cover_thumbnail_url" :src="album.cover_thumbnail_url" :alt="album.title" loading="lazy" class="ds-rect-inner" style="object-fit: cover" />
              <div v-else class="ds-rect-inner ds-placeholder">{{ album.title }}</div>
            </div>
            <p style="font-family: var(--ds-font-display); font-size: var(--ds-text-subtitle); font-weight: 400; line-height: 1.3; color: var(--ds-action-primary); margin-top: var(--ds-space-2)"><span v-if="album.published === false" class="ds-badge ds-badge-neutral draft-pill">Draft</span> {{ album.title }}</p>
          </router-link>
        </div>
        <div style="text-align: center; margin-top: var(--ds-space-6)">
          <BaseButton to="/gallery" variant="accent-outline">View gallery</BaseButton>
        </div>
      </div>
    </section>

    <SponsorsMarquee v-if="moduleEnabled('sponsors')" />
  </div>
</template>
