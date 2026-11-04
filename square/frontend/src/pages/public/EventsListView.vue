<script setup lang="ts">
import { calendarFeedUrl, calendarSubscribeUrl } from '../../services/eventSeriesApi'
import EventsBlock from '../../layout-themes/sections/EventsBlock.vue'
import PageHeading from '../../layout-themes/parts/PageHeading.vue'
import { activeLayout } from '../../layout-themes/layouts'
const themed = activeLayout !== null // a layout theme sets the page heading and lists (W9-R5)
import { squareProfile } from '../../services/squareConfig'
import { usePageHeading } from '../../composables/usePageHeading'
import { ref, computed, watch, onMounted } from 'vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchEvents, type EventSummary } from '../../services/eventsApi'
import { formatDateTime, formatEventDate } from '../../utils/date'
import { ensureMinLoadingDuration } from '../../utils/minLoadingDuration'
import { useLookup } from '../../composables/useLookup'

const when = ref('upcoming')
const eventType = ref('')
const page = ref(1)
const perPage = 6

const events = ref<EventSummary[]>([])
const totalPages = ref(1)
const loading = ref(true)
const error = ref(false)

const tabs = [
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'past', label: 'Past' },
]

const { options: eventTypes, label: eventTypeLabel } = useLookup('event_type')
const typeOptions = computed(() => [{ value: '', label: 'All types' }, ...eventTypes.value])

async function loadEvents() {
  loading.value = true
  error.value = false
  const startedAt = Date.now()
  try {
    const data = await fetchEvents({
      when: when.value,
      type: eventType.value || undefined,
      page: page.value,
      perPage,
    })
    events.value = data.items
    totalPages.value = data.total_pages
  } catch {
    error.value = true
    events.value = []
  } finally {
    await ensureMinLoadingDuration(startedAt)
    loading.value = false
  }
}

watch([when, eventType], () => {
  page.value = 1
  loadEvents()
})
watch(page, loadEvents)

onMounted(loadEvents)

// Mirrors the design system's own Pagination component: always show first, last, and the
// current page, filling in neighbours until `span` slots are used, collapsing gaps with "…".
function pageList(current: number, total: number, span: number): (number | string)[] {
  if (total <= span) return Array.from({ length: total }, (_, i) => i + 1)
  const out = new Set([1, total, current])
  for (let d = 1; out.size < span && d < total; d++) {
    if (current - d > 1) out.add(current - d)
    if (out.size < span && current + d < total) out.add(current + d)
  }
  const sorted = [...out].sort((a, b) => a - b)
  const withGaps: (number | string)[] = []
  sorted.forEach((n, i) => {
    if (i > 0 && n - sorted[i - 1] > 1) withGaps.push(`gap-${n}`)
    withGaps.push(n)
  })
  return withGaps
}

const pages = computed(() => pageList(page.value, totalPages.value, 5))

function goToPage(n: number) {
  if (n >= 1 && n <= totalPages.value) page.value = n
}
const heading = usePageHeading('events', () => ({ eyebrow: 'Programme', title: 'Events', intro: `Upcoming and past gatherings at ${squareProfile.name}.` }))

const feedCopied = ref(false)
async function copyFeed() {
  try {
    await navigator.clipboard.writeText(calendarFeedUrl())
    feedCopied.value = true
    setTimeout(() => (feedCopied.value = false), 2000)
  } catch {
    /* the link is also shown as a link to click */
  }
}
</script>

<template>
  <div class="ds-scope">
    <PageHeading v-if="themed" :heading="heading" />
    <section v-else class="ds-band ds-band-wash" style="padding-bottom: var(--ds-space-6)">
      <div class="ds-container ds-heading">
        <span v-if="heading.script_line" class="ds-script">{{ heading.script_line }}</span>
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />{{ heading.eyebrow }}</span>
        <h1 class="ds-display ds-display-m">{{ heading.title }}</h1>
        <p v-if="heading.local_line" class="ds-bn" style="font-size: var(--ds-text-subtitle); color: var(--ds-text-muted)">{{ heading.local_line }}</p>
        <p class="ds-intro">{{ heading.intro }}</p>
      </div>
    </section>

    <section class="ds-band ds-band-paper" style="padding-top: var(--ds-space-6)">
      <div class="ds-container" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
        <div style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
          <div class="ds-tabs">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              type="button"
              class="ds-tab"
              :class="{ 'ds-tab-active': when === tab.id }"
              @click="when = tab.id"
            >
              {{ tab.label }}
            </button>
          </div>
          <div style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
            <button
              v-for="opt in typeOptions"
              :key="opt.value"
              type="button"
              class="ds-tag"
              :class="{ 'ds-tag-selected': eventType === opt.value }"
              @click="eventType = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <p class="ds-meta calendar-subscribe" style="display: flex; gap: var(--ds-space-3); flex-wrap: wrap; align-items: center">
          <a :href="calendarSubscribeUrl()" class="subscribe-link" style="font-weight: 600">Add these events to your calendar</a>
          <button type="button" class="ds-tag copy-feed" @click="copyFeed">{{ feedCopied ? 'Copied!' : 'Copy the calendar link' }}</button>
        </p>

        <BaseLoadingState v-if="loading" label="Loading events…" />
        <BaseEmptyState
          v-else-if="error"
          title="Couldn't load events"
          description="Please try again shortly."
        />
        <BaseEmptyState
          v-else-if="events.length === 0"
          title="No events found"
          description="Try a different filter."
        />
        <template v-else>
          <EventsBlock v-if="themed" :items="events" />
          <div v-else class="ds-cards ds-cards--3">
            <router-link
              v-for="event in events"
              :key="event.id"
              :to="`/events/${event.slug}`"
              class="ds-event-card"
              :class="{ 'ds-event-card-draft': !event.published }"
            >
              <div class="ds-event-media" :class="{ 'ds-placeholder': !event.banner_image }">
                <img v-if="event.banner_image" :src="event.banner_image" :alt="event.title" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover" />
                <span class="ds-badge ds-badge-accent" style="position: relative">{{ eventTypeLabel(event.event_type) }}</span>
                <span v-if="!event.published" class="ds-badge ds-badge-neutral" style="position: relative">Draft</span>
                <span v-else-if="event.status === 'cancelled'" class="ds-badge ds-badge-neutral cancelled-pill" style="position: relative">Cancelled</span>
                <span v-else-if="event.sales_closed" class="ds-badge ds-badge-neutral sales-closed-pill" style="position: relative">Sales closed</span>
                <span v-else-if="event.sales_not_open && event.sales_open_at" class="ds-badge ds-badge-accent sales-not-open-pill" style="position: relative; gap: 4px"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg>Tickets open {{ formatDateTime(event.sales_open_at) }}</span>
              </div>
              <div class="ds-event-body">
                <p class="ds-meta">{{ formatEventDate(event.start_datetime) }}</p>
                <h2 class="ds-event-title">{{ event.title }}</h2>
                <p v-if="event.venue" class="ds-meta">{{ event.venue }}</p>
                <p v-if="event.short_description" class="ds-body ds-desc-s" :data-desc-style="event.description_style ?? undefined">{{ event.short_description }}</p>
                <span class="ds-event-cta">Details →</span>
              </div>
            </router-link>
          </div>

          <nav v-if="totalPages > 1" class="ds-pagination" aria-label="Pagination">
            <div class="ds-pagination-group">
              <button class="ds-page-step" :disabled="page <= 1" aria-label="Previous page" @click="goToPage(page - 1)">
                ← Prev
              </button>
              <template v-for="n in pages" :key="n">
                <span v-if="typeof n === 'string'" class="ds-page-gap" aria-hidden="true">…</span>
                <button
                  v-else
                  type="button"
                  class="ds-page-btn"
                  :class="{ 'ds-page-btn-active': n === page }"
                  :aria-current="n === page ? 'page' : undefined"
                  @click="goToPage(n)"
                >
                  {{ n }}
                </button>
              </template>
              <button class="ds-page-step" :disabled="page >= totalPages" aria-label="Next page" @click="goToPage(page + 1)">
                Next →
              </button>
            </div>
          </nav>
        </template>
      </div>
    </section>
  </div>
</template>
