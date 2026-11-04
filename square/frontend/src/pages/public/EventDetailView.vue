<script setup lang="ts">
import { eventCalendarFileUrl } from '../../services/eventSeriesApi'
import { moduleEnabled } from '../../services/modules'
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import DOMPurify from 'dompurify'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseBreadcrumbs from '../../components/ui/BaseBreadcrumbs.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import BannerImage from '../../components/ui/BannerImage.vue'
import DonateModal from '../../components/DonateModal.vue'
import SponsorEnquiryModal from '../../components/SponsorEnquiryModal.vue'
import { fetchSupportOptions, type SupportOptions } from '../../services/eventSupportApi'
import {
  fetchEvent,
  fetchEventQr,
  EventNotFoundError,
  type EventDetail,
  type EventSessionRecord,
} from '../../services/eventsApi'
import { fetchAlbums, type AlbumSummary } from '../../services/galleryApi'
import { fetchTicketTypes, type TicketTypeSummary } from '../../services/ticketsApi'
import { formatDateTime, formatEventDate, formatScheduleDay } from '../../utils/date'
import { downloadEventIcs } from '../../utils/calendar'
import { formatPrice } from '../../utils/money'
import { useLookup } from '../../composables/useLookup'
import { ensureMinLoadingDuration } from '../../utils/minLoadingDuration'
import { setPageMeta } from '../../composables/usePageMeta'
import { useToast } from '../../composables/useToast'

const route = useRoute()

const event = ref<EventDetail | null>(null)
const loading = ref(true)
const notFound = ref(false)
const error = ref(false)
const albums = ref<AlbumSummary[]>([])
const ticketTypes = ref<TicketTypeSummary[]>([])
const hasTicketTypes = computed(() => ticketTypes.value.length > 0)
const sanitizedDescription = computed(() => DOMPurify.sanitize(event.value?.description ?? ''))
// The slider combines the legacy single banner_image (shown first, as "the main banner")
// with every admin-uploaded EventBanner — they're one continuous slideshow, not alternatives.
// An event with neither falls back to a tagged gallery album's cover.
const bannerIndex = ref(0)
const sliderImages = computed(() => {
  const images: string[] = []
  if (event.value?.banner_image) images.push(event.value.banner_image)
  images.push(...(event.value?.banners ?? []).map((b) => b.image_url))
  return images
})
const hasBannerSlider = computed(() => sliderImages.value.length > 1)
const heroImage = computed(() => sliderImages.value[bannerIndex.value] ?? albums.value[0]?.cover_thumbnail_url ?? null)

function showPreviousBanner() {
  if (!sliderImages.value.length) return
  bannerIndex.value = (bannerIndex.value - 1 + sliderImages.value.length) % sliderImages.value.length
  restartAutoplay()
}

function showNextBanner() {
  if (!sliderImages.value.length) return
  bannerIndex.value = (bannerIndex.value + 1) % sliderImages.value.length
  restartAutoplay()
}

function goToBanner(index: number) {
  bannerIndex.value = index
  restartAutoplay()
}

// Auto-advance every 3s, same slides the arrows/dots/swipe already navigate — paused rather
// than stopped outright while the lightbox is open (reopening the page's slider shouldn't
// have silently drifted) or while a visitor's cursor is actually over it (WCAG 2.2.2 — motion
// that starts on its own and doesn't stop needs an easy way to pause it), and skipped
// entirely under prefers-reduced-motion. Manual navigation (buttons/dots/swipe, above) always
// restarts the 3s window so the next auto-advance never lands right on top of an interaction.
const AUTOPLAY_INTERVAL_MS = 3000
const autoplayPausedByHover = ref(false)
let autoplayTimer: ReturnType<typeof setInterval> | null = null

function stopAutoplay() {
  if (autoplayTimer !== null) {
    clearInterval(autoplayTimer)
    autoplayTimer = null
  }
}

function startAutoplay() {
  stopAutoplay()
  if (!hasBannerSlider.value || lightboxOpen.value || autoplayPausedByHover.value) return
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches) return
  autoplayTimer = setInterval(showNextBanner, AUTOPLAY_INTERVAL_MS)
}

function restartAutoplay() {
  startAutoplay()
}

function pauseAutoplayOnHover() {
  // Mobile browsers fire a synthetic mouseenter on tap (with no matching mouseleave ever
  // coming — there's no cursor to "leave"), so without this guard the very first touch on the
  // banner (including the swipe gesture itself) would permanently stop autoplay on phones/
  // tablets. (hover: hover) is false for a touch-only primary input, true for a real mouse.
  if (!window.matchMedia?.('(hover: hover)')?.matches) return
  autoplayPausedByHover.value = true
  stopAutoplay()
}

function resumeAutoplayAfterHover() {
  autoplayPausedByHover.value = false
  startAutoplay()
}

onUnmounted(stopAutoplay)

// Same inline touch-swipe pattern as GalleryAlbumView.vue's lightbox — no gesture library,
// just a touchstart/touchend delta-X check. Shared by the inline hero banner and the lightbox
// image below (both call the exact same next/previous banner functions).
const SWIPE_THRESHOLD_PX = 40
let touchStartX: number | null = null

function onBannerTouchStart(event: TouchEvent) {
  touchStartX = event.touches[0]?.clientX ?? null
}

function onBannerTouchEnd(event: TouchEvent) {
  if (touchStartX === null || !hasBannerSlider.value) return
  const touchEndX = event.changedTouches[0]?.clientX ?? touchStartX
  const delta = touchEndX - touchStartX
  if (delta > SWIPE_THRESHOLD_PX) {
    showPreviousBanner()
  } else if (delta < -SWIPE_THRESHOLD_PX) {
    showNextBanner()
  }
  touchStartX = null
}

// Click-to-open, click-to-zoom lightbox — a plain photo-viewer affordance, independent of
// the slider's own arrows/dots (which call @click.stop so they never also open this).
const lightboxOpen = ref(false)
const zoomed = ref(false)

function openLightbox() {
  if (!heroImage.value) return
  zoomed.value = false
  lightboxOpen.value = true
}

// The lightbox frame's width comes from plain CSS shrink-to-fit (BaseModal's `hug-content`
// prop → .ds-modal-hug { width: fit-content }), not a JS measurement of the photo's natural
// size: an <img> with only max-height set derives its own rendered width from its natural
// aspect ratio, and a fit-content ancestor picks that up natively. See design-system.css's
// .ds-modal-hug comment for the fuller history (a prior JS-computed-width attempt here left
// the modal's own box a fixed wide size regardless of the photo's shape).
const lightboxFrameStyle = {
  width: '100%',
  maxHeight: '80vh',
  overflow: 'auto',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--ds-surface-sunken)',
  borderRadius: 'var(--ds-radius-md)',
  touchAction: 'pan-y pinch-zoom',
}

watch(lightboxOpen, (open) => {
  if (open) {
    stopAutoplay()
  } else {
    zoomed.value = false
    startAutoplay()
  }
})

watch(bannerIndex, () => {
  zoomed.value = false
})

const cheapestTicketPrice = computed(() => {
  if (!ticketTypes.value.length) return null
  return Math.min(...ticketTypes.value.map((t) => t.price))
})

// Sessions arrive pre-ordered by sort_order; group consecutive rows sharing a
// day_label under one header rather than maintaining a separate "day" table.
const eventHasEnded = computed(() => {
  if (!event.value) return false
  const reference = event.value.end_datetime ?? event.value.start_datetime
  return new Date(reference).getTime() < Date.now()
})

const directionsUrl = computed(() => {
  if (!event.value) return null
  const parts = [event.value.venue, event.value.address].filter(Boolean)
  if (parts.length === 0) return null
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(parts.join(', '))}`
})

const toast = useToast()
const { label: eventTypeLabel } = useLookup('event_type')
const shareOpen = ref(false)
// Donations and sponsorship enquiries: open only while the event is published and not over.
const support = ref<SupportOptions | null>(null)
const donateOpen = ref(false)
const sponsorOpen = ref(false)
const shareQr = ref<string | null>(null)
const shareUrl = computed(() => `${window.location.origin}/events/${event.value?.slug ?? ''}`)

async function openShare() {
  shareOpen.value = true
  if (shareQr.value || !event.value) return
  try {
    shareQr.value = (await fetchEventQr(event.value.slug)).qr
  } catch {
    toast.error("Couldn't load the QR code.")
  }
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    toast.success('Link copied')
  } catch {
    toast.error("Couldn't copy the link.")
  }
}

async function copyQr() {
  if (!shareQr.value) return
  try {
    const blob = await (await fetch(shareQr.value)).blob()
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
    toast.success('QR copied')
  } catch {
    toast.error("Couldn't copy the QR code.")
  }
}

function addToCalendar() {
  if (!event.value) return
  downloadEventIcs({
    id: event.value.id,
    title: event.value.title,
    description: event.value.description,
    startDatetime: event.value.start_datetime,
    endDatetime: event.value.end_datetime,
    venue: event.value.venue,
    address: event.value.address,
  })
}

const scheduleGroups = computed(() => {
  const groups: { day_label: string; sessions: EventSessionRecord[] }[] = []
  for (const session of event.value?.sessions ?? []) {
    const lastGroup = groups[groups.length - 1]
    if (lastGroup && lastGroup.day_label === session.day_label) {
      lastGroup.sessions.push(session)
    } else {
      groups.push({ day_label: session.day_label, sessions: [session] })
    }
  }
  return groups
})

async function load(slug: string) {
  stopAutoplay()
  loading.value = true
  notFound.value = false
  error.value = false
  event.value = null
  albums.value = []
  ticketTypes.value = []
  bannerIndex.value = 0
  const startedAt = Date.now()
  try {
    event.value = await fetchEvent(slug)
    setPageMeta(event.value.title, event.value.short_description ?? undefined)
    startAutoplay()
  } catch (err) {
    if (err instanceof EventNotFoundError) {
      notFound.value = true
    } else {
      error.value = true
    }
  } finally {
    await ensureMinLoadingDuration(startedAt)
    loading.value = false
  }

  if (event.value) {
    try {
      if (moduleEnabled('gallery')) albums.value = (await fetchAlbums(1, 20, event.value.id)).items
    } catch {
      // Photos are a secondary section — an album-fetch failure shouldn't block the page.
    }

    support.value = await fetchSupportOptions(event.value.slug)

    try {
      if (moduleEnabled('tickets')) ticketTypes.value = (await fetchTicketTypes(event.value.id)).items // W8-R29: tickets are the Tickets module's
    } catch {
      // Whether to show "Buy tickets" is secondary — a failed fetch just hides it rather
      // than blocking the page; the tickets page itself will surface a real error on its own.
    }
  }
}

onMounted(() => load(route.params.slug as string))
watch(
  () => route.params.slug,
  (slug) => load(slug as string),
)
</script>

<template>
  <div class="ds-scope">
    <section class="ds-band ds-band-wash" style="padding-bottom: var(--ds-space-6)">
      <div class="ds-container">
        <BaseBreadcrumbs
          :items="[{ label: 'Home', to: '/' }, { label: 'Events', to: '/events' }, ...(event ? [{ label: event.title }] : [])]"
          style="display: block; margin-bottom: var(--ds-space-5)"
        />

        <BaseLoadingState v-if="loading" label="Loading event…" />
        <BaseEmptyState
          v-else-if="notFound"
          title="Event not found"
          description="This event may have been removed or is no longer published."
        />
        <BaseEmptyState
          v-else-if="error"
          title="Couldn't load this event"
          description="Please try again shortly."
        />
        <div v-else-if="event" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
          <div class="ds-heading event-head event-head-panel" style="max-width: none">
            <span class="ds-eyebrow">
              <span class="ds-eyebrow-rule" />{{ eventTypeLabel(event.event_type) }}
              <span v-if="!event.published" class="ds-badge ds-badge-neutral" style="margin-left: var(--ds-space-2)">Draft</span>
              <span v-else-if="event.status === 'cancelled'" class="ds-badge ds-badge-neutral cancelled-pill" style="margin-left: var(--ds-space-2)">Cancelled</span>
            </span>
            <h1 class="ds-display ds-display-l">{{ event.title }}</h1>
            <p v-if="event.sub_name" class="ds-bn event-head-sub">{{ event.sub_name }}</p>
            <div class="event-head-meta">
              <div class="event-head-items">
                <button type="button" class="event-head-item event-head-link" title="Add to calendar" @click="addToCalendar">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2v4" /><path d="M16 2v4" /><rect width="18" height="18" x="3" y="4" rx="2" /><path d="M3 10h18" /></svg>
                  <span>{{ formatEventDate(event.start_datetime) }}<template v-if="event.end_datetime"> – {{ formatEventDate(event.end_datetime) }}</template></span>
                </button>
                <component
                  :is="directionsUrl ? 'a' : 'span'"
                  v-if="event.venue"
                  class="event-head-item"
                  :class="{ 'event-head-link': directionsUrl }"
                  :href="directionsUrl || undefined"
                  :target="directionsUrl ? '_blank' : undefined"
                  :rel="directionsUrl ? 'noopener noreferrer' : undefined"
                  :title="directionsUrl ? 'Get directions' : undefined"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0" /><circle cx="12" cy="10" r="3" /></svg>
                  <span>{{ event.venue }}</span>
                </component>
              </div>
              <div class="event-head-actions">
                <BaseButton
                  v-if="!eventHasEnded && hasTicketTypes && !event.sales_closed && !event.sales_not_open"
                  :to="`/events/${event.slug}/tickets`"
                  size="md"
                  class="event-head-buy"
                >
                  Buy tickets
                </BaseButton>
                <p v-else-if="eventHasEnded" class="ds-meta event-head-buy">This event has already taken place.</p>
                <p v-else-if="event.sales_closed && hasTicketTypes" class="ds-meta event-head-buy sales-closed-note">Ticket sales have closed.</p>
                <p v-else-if="event.sales_not_open && event.sales_open_at && hasTicketTypes" class="ds-sales-callout event-head-buy"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg><span><strong>Tickets on sale soon</strong> · opens {{ formatDateTime(event.sales_open_at) }}</span></p>

                <BaseButton v-if="support?.donations_open" variant="secondary" size="md" class="event-head-donate" @click="donateOpen = true">
                  Donate
                </BaseButton>
                <BaseButton v-if="support?.sponsorships_open" variant="secondary" size="md" class="event-head-sponsor" @click="sponsorOpen = true">
                  Become a sponsor
                </BaseButton>

                <div class="event-head-capsule">
                  <a v-if="event.facebook_url" :href="event.facebook_url" target="_blank" rel="noopener noreferrer" class="event-head-capsule-btn" aria-label="Facebook event page" title="Facebook event page">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" /></svg>
                  </a>
                  <a v-if="event.instagram_url" :href="event.instagram_url" target="_blank" rel="noopener noreferrer" class="event-head-capsule-btn" aria-label="Instagram event page" title="Instagram event page">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="20" height="20" x="2" y="2" rx="5" ry="5" /><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" /><line x1="17.5" x2="17.51" y1="6.5" y2="6.5" /></svg>
                  </a>
                  <span v-if="event.facebook_url || event.instagram_url" class="event-head-capsule-divider" aria-hidden="true"></span>
                  <a :href="eventCalendarFileUrl(event.slug)" class="event-head-capsule-btn add-to-calendar" aria-label="Add to calendar" title="Add to calendar" download>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="18" height="18" x="3" y="4" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></svg>
                  </a>
                  <button type="button" class="event-head-capsule-btn" aria-label="Share" title="Share" @click="openShare">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><line x1="8.59" x2="15.42" y1="13.51" y2="17.49" /><line x1="15.41" x2="8.59" y1="6.51" y2="10.49" /></svg>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div
            class="ds-banner"
            style="width: 100%; position: relative; touch-action: pan-y"
            @touchstart="onBannerTouchStart"
            @touchend="onBannerTouchEnd"
            @mouseenter="pauseAutoplayOnHover"
            @mouseleave="resumeAutoplayAfterHover"
          >
            <div :style="{ cursor: heroImage ? 'zoom-in' : 'default' }" @click="openLightbox">
              <BannerImage :src="heroImage" :alt="event.title" />
            </div>
            <template v-if="hasBannerSlider">
              <button
                type="button"
                class="ds-icon-btn ds-icon-btn-scrim"
                aria-label="Previous banner" title="Previous banner"
                style="position: absolute; top: 50%; left: var(--ds-space-3); transform: translateY(-50%)"
                @click.stop="showPreviousBanner"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
              </button>
              <button
                type="button"
                class="ds-icon-btn ds-icon-btn-scrim"
                aria-label="Next banner" title="Next banner"
                style="position: absolute; top: 50%; right: var(--ds-space-3); transform: translateY(-50%)"
                @click.stop="showNextBanner"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
              </button>
              <div class="ds-dot-bar" style="position: absolute; bottom: var(--ds-space-3); left: 50%; transform: translateX(-50%)">
                <button
                  v-for="(image, dotIndex) in sliderImages"
                  :key="image + dotIndex"
                  type="button"
                  class="ds-testimonial-dot"
                  :class="{ 'ds-testimonial-dot-active': dotIndex === bannerIndex }"
                  :aria-label="`Go to banner ${dotIndex + 1}`"
                  @click.stop="goToBanner(dotIndex)"
                />
              </div>
            </template>
          </div>

          <DonateModal v-if="support?.donations_open" v-model="donateOpen" :slug="event.slug" :event-title="event.title" :methods="support.payment_methods" />
          <SponsorEnquiryModal v-if="support?.sponsorships_open" v-model="sponsorOpen" :slug="event.slug" :event-title="event.title" />

          <BaseModal v-model="shareOpen" title="Share this event" aria-label="Share this event">
            <div style="display: flex; flex-direction: column; align-items: center; gap: var(--ds-space-4)">
              <img v-if="shareQr" :src="shareQr" alt="QR code for this event page" style="width: 200px; height: 200px" />
              <BaseLoadingState v-else />
              <div style="display: flex; gap: var(--ds-space-3); flex-wrap: wrap; justify-content: center">
                <BaseButton variant="secondary" @click="copyLink">Copy link</BaseButton>
                <BaseButton variant="secondary" :disabled="!shareQr" @click="copyQr">Copy QR</BaseButton>
              </div>
            </div>
          </BaseModal>

          <BaseModal v-model="lightboxOpen" size="xl" hug-content aria-label="Event photo">
            <!-- Arrow/dot chrome overlays this wrapper's own edges rather than sitting in a
                 row below the image (that's what used to make controls jump sideways between
                 a portrait and a landscape photo). BaseModal's hug-content prop shrinks the
                 modal box itself to the photo's own rendered width (see design-system.css's
                 .ds-modal-hug comment) — this wrapper just needs to be a positioning context
                 for the buttons below, which then sit flush against the actual image edges. -->
            <div v-if="heroImage" style="position: relative">
              <div
                :style="lightboxFrameStyle"
                @touchstart="onBannerTouchStart"
                @touchend="onBannerTouchEnd"
              >
                <img
                  :src="heroImage"
                  :alt="event.title"
                  :style="{
                    cursor: zoomed ? 'zoom-out' : 'zoom-in',
                    transform: zoomed ? 'scale(2)' : 'scale(1)',
                    transition: 'transform 150ms ease',
                    maxWidth: '100%',
                    maxHeight: '80vh',
                    display: 'block',
                  }"
                  @click="zoomed = !zoomed"
                />
              </div>
              <template v-if="hasBannerSlider">
                <button
                  type="button"
                  class="ds-icon-btn ds-icon-btn-scrim"
                  aria-label="Previous banner" title="Previous banner"
                  style="position: absolute; top: 50%; left: var(--ds-space-3); transform: translateY(-50%)"
                  @click.stop="showPreviousBanner"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
                </button>
                <button
                  type="button"
                  class="ds-icon-btn ds-icon-btn-scrim"
                  aria-label="Next banner" title="Next banner"
                  style="position: absolute; top: 50%; right: var(--ds-space-3); transform: translateY(-50%)"
                  @click.stop="showNextBanner"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
                </button>
                <div class="ds-dot-bar" style="position: absolute; bottom: var(--ds-space-3); left: 50%; transform: translateX(-50%)">
                  <button
                    v-for="(image, dotIndex) in sliderImages"
                    :key="image + dotIndex"
                    type="button"
                    class="ds-testimonial-dot"
                    :class="{ 'ds-testimonial-dot-active': dotIndex === bannerIndex }"
                    :aria-label="`Go to banner ${dotIndex + 1}`"
                    @click.stop="goToBanner(dotIndex)"
                  />
                </div>
              </template>
            </div>
          </BaseModal>

          <div>
            <div v-if="event.description" class="event-description ds-intro ds-desc" :data-desc-style="event.description_style ?? undefined" style="max-width: none" v-html="sanitizedDescription"></div>
          </div>
        </div>
      </div>
    </section>

    <section v-if="event" class="ds-band ds-band-paper" style="padding-top: var(--ds-space-7); padding-bottom: var(--ds-space-7)">
      <div class="ds-container ds-row ds-row--sidebar">
        <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
          <section v-if="scheduleGroups.length" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
            <h2 class="ds-title">Schedule</h2>
            <div class="ds-motif" style="max-width: none; margin: 0"><span></span><span class="ds-motif-glyph">❖</span><span></span></div>
            <div v-for="group in scheduleGroups" :key="group.day_label">
              <h3 class="ds-eyebrow" style="margin-bottom: var(--ds-space-3)">{{ formatScheduleDay(group.day_label) }}</h3>
              <div class="ds-table-wrap">
                <div class="ds-table-scroll">
                  <table class="ds-table" style="min-width: 0">
                    <tbody>
                      <tr v-for="session in group.sessions" :key="session.id">
                        <td style="width: 96px; white-space: nowrap; color: var(--ds-text-muted); font-variant-numeric: tabular-nums">{{ session.time }}</td>
                        <td data-emphasis>
                          {{ session.title }}
                          <div v-if="session.description" class="ds-caption" style="margin-top: 2px; font-weight: 400">{{ session.description }}</div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </section>


          <section v-if="albums.length">
            <h2 class="ds-title" style="margin-bottom: var(--ds-space-4)">Photos</h2>
            <div class="ds-gallery-grid">
              <router-link v-for="album in albums" :key="album.id" :to="`/gallery/${album.id}`" class="ds-gallery-item">
                <div class="ds-rect" style="aspect-ratio: 1">
                  <img
                    v-if="album.cover_thumbnail_url"
                    :src="album.cover_thumbnail_url"
                    :alt="album.title"
                    class="ds-rect-inner"
                    style="object-fit: cover"
                  />
                  <div v-else class="ds-rect-inner ds-placeholder">No photos yet</div>
                </div>
                <p class="ds-meta" style="margin-top: var(--ds-space-2)">{{ album.title }}</p>
              </router-link>
            </div>
          </section>
        </div>

        <aside class="ds-card" style="position: sticky; top: calc(var(--ds-nav-height) + var(--ds-space-5))">
          <div class="ds-deflist" style="grid-template-columns: 1fr">
            <div class="ds-deflist-row" style="padding: 0 0 var(--ds-space-3)">
              <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-1)">When</p>
              <p class="ds-body">
                {{ formatEventDate(event.start_datetime) }}
                <span v-if="event.end_datetime"> – {{ formatEventDate(event.end_datetime) }}</span>
              </p>
            </div>
            <div v-if="event.venue" class="ds-deflist-row" style="padding: var(--ds-space-3) 0">
              <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-1)">Where</p>
              <p class="ds-body">{{ event.venue }}<span v-if="event.address">, {{ event.address }}</span></p>
            </div>
            <div v-if="hasTicketTypes && cheapestTicketPrice !== null" class="ds-deflist-row" style="padding: var(--ds-space-3) 0">
              <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-1)">Tickets</p>
              <p class="ds-body">From {{ formatPrice(cheapestTicketPrice) }}</p>
            </div>
            <div v-if="moduleEnabled('tickets') && event.capacity" class="ds-deflist-row" style="padding: var(--ds-space-3) 0 0; border-bottom: none">
              <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-1)">Capacity</p>
              <p class="ds-body">{{ event.capacity }}</p>
            </div>
          </div>

          <p v-if="!eventHasEnded && hasTicketTypes && event.sales_closed" class="ds-meta sales-closed-note" style="margin-top: var(--ds-space-5); text-align: center">Ticket sales have closed.</p>
          <p v-if="!eventHasEnded && hasTicketTypes && event.sales_not_open && event.sales_open_at" class="ds-sales-callout" style="margin-top: var(--ds-space-5)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg><span><strong>Tickets on sale soon</strong> · opens {{ formatDateTime(event.sales_open_at) }}</span></p>
          <BaseButton
            v-if="!eventHasEnded && hasTicketTypes && !event.sales_closed && !event.sales_not_open"
            :to="`/events/${event.slug}/tickets`"
            full-width
            style="margin-top: var(--ds-space-5)"
          >
            Buy tickets
          </BaseButton>
          <BaseButton v-if="support?.donations_open" variant="secondary" full-width class="support-donate" style="margin-top: var(--ds-space-2)" @click="donateOpen = true">
            Donate
          </BaseButton>
          <BaseButton v-if="support?.sponsorships_open" variant="secondary" full-width class="support-sponsor" style="margin-top: var(--ds-space-2)" @click="sponsorOpen = true">
            Become a sponsor
          </BaseButton>
          <BaseButton to="/events" variant="ghost" full-width style="margin-top: var(--ds-space-2)">
            Back to programme
          </BaseButton>
        </aside>
      </div>
    </section>
  </div>
</template>

<style scoped>
.event-head-panel {
  position: relative;
  padding: var(--ds-space-6) var(--ds-space-6) var(--ds-space-5);
}
.event-head-sub {
  margin: calc(-1 * var(--ds-space-1)) 0 0;
  font-size: var(--ds-text-body-m);
  color: var(--ds-text-primary);
}
.event-head-actions {
  display: flex;
  align-items: center;
  gap: var(--ds-space-3);
  flex-wrap: wrap;
  margin-left: auto;
  justify-content: flex-end;
}
/* Page-header pattern (design system "Page header & breadcrumbs"): date/venue are the calendar and
   map links; at most one CTA + one hairline capsule (Facebook, Instagram | Share). */
.event-head-items {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ds-space-2) var(--ds-space-6);
}
.event-head-link {
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
  text-decoration: none;
}
.event-head-link span {
  text-decoration: underline dotted;
  text-decoration-thickness: 1px;
  text-underline-offset: 4px;
  text-decoration-color: var(--ds-border-strong);
  transition: text-decoration-color 150ms;
}
.event-head-link:hover span,
.event-head-link:focus-visible span {
  text-decoration-color: var(--ds-action-primary);
}
.event-head-capsule {
  display: inline-flex;
  align-items: stretch;
  height: 40px;
  border: 1px solid var(--ds-border-hairline);
  border-radius: 999px;
  background: color-mix(in oklab, var(--ds-surface-card) 60%, transparent);
}
.event-head-capsule-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--ds-text-body);
  cursor: pointer;
  transition: color 150ms, background 150ms;
}
.event-head-capsule-btn:hover,
.event-head-capsule-btn:active,
.event-head-capsule-btn:focus-visible {
  background: var(--ds-surface-sunken);
  color: var(--ds-action-primary);
}
.event-head-capsule-divider {
  width: 1px;
  margin: 10px 2px;
  background: var(--ds-border-hairline);
}
.event-head-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--ds-space-2) var(--ds-space-6);
  width: 100%;
  margin-top: var(--ds-space-2);
  padding-top: var(--ds-space-4);
  border-top: 1px solid var(--ds-border-hairline);
}
.event-head-item {
  display: inline-flex;
  align-items: center;
  gap: var(--ds-space-2);
  font-size: var(--ds-text-body-m);
  color: var(--ds-text-body);
}
.event-head-item svg {
  color: var(--ds-terracotta-400);
  flex-shrink: 0;
}
/* Preserves line breaks in older plain-text descriptions written before this rich-text editor
   existed — new content's compact HTML (no stray newlines between tags) is unaffected. */
.event-description {
  white-space: pre-line;
}
.event-description :deep(h2) {
  font-family: var(--ds-font-display);
  font-size: var(--ds-text-title);
  margin: 1.5rem 0 0.5rem;
}
.event-description :deep(h3) {
  font-family: var(--ds-font-display);
  font-size: var(--ds-text-subtitle);
  margin: 1.25rem 0 0.5rem;
}
.event-description :deep(p) {
  margin: 0.75rem 0;
}
.event-description :deep(ul),
.event-description :deep(ol) {
  margin: 0.75rem 0;
  padding-left: 1.5rem;
}
.event-description :deep(ul) {
  list-style: disc;
}
.event-description :deep(ol) {
  list-style: decimal;
}
.event-description :deep(a) {
  color: var(--ds-text-primary);
  text-decoration: underline;
}

@media (max-width: 640px) {
  .event-head-panel {
    padding: var(--ds-space-5) var(--ds-space-4) var(--ds-space-4);
  }
  .event-head-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--ds-space-3);
  }
  .event-head-actions {
    width: 100%;
    margin-left: 0;
    justify-content: center;
    flex-wrap: wrap;
    gap: var(--ds-space-2);
    padding-top: var(--ds-space-3);
    border-top: 1px solid var(--ds-border-hairline);
  }
  .event-head-buy {
    flex: 0 0 80%;
    margin-inline: 10%; /* margins fill the row so the icons always start a new line */
    text-align: center;
  }
}
</style>
