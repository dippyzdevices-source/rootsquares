<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import FilterPills from '../../components/ui/FilterPills.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchAdminEvents, type AdminEvent } from '../../services/adminEventsApi'
import { formatEventDate } from '../../utils/date'
import { eventPhase, EVENT_PHASE_BADGE, EVENT_PHASE_LABEL, type EventPhase } from '../../utils/eventPhase'

const events = ref<AdminEvent[]>([])
const loading = ref(true)
const error = ref(false)
const search = ref('')

const phaseFilter = ref<'all' | EventPhase>('all')
const phaseFilters: { value: 'all' | EventPhase; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'live', label: 'Live' },
  { value: 'draft', label: 'Draft' },
  { value: 'expired', label: 'Expired' },
]

const filteredEvents = computed(() => {
  const q = search.value.trim().toLowerCase()
  return events.value.filter(
    (event) =>
      (phaseFilter.value === 'all' || eventPhase(event) === phaseFilter.value) &&
      (!q || event.title.toLowerCase().includes(q)),
  )
})

// Events already arrive ordered most-recent-first (see admin_routes.py's
// `order_by(Event.start_datetime.desc())`), so grouping while preserving that order gives
// years most-recent-first for free, with each year's own events already sorted too.
const groupedByYear = computed(() => {
  const groups = new Map<number, AdminEvent[]>()
  for (const event of filteredEvents.value) {
    const year = new Date(event.start_datetime).getFullYear()
    const bucket = groups.get(year)
    if (bucket) {
      bucket.push(event)
    } else {
      groups.set(year, [event])
    }
  }
  return [...groups.entries()].map(([year, items]) => ({ year, items }))
})

onMounted(async () => {
  try {
    // A generous per_page — this is a "pick an event" list, not a paginated browse; reuses
    // the existing admin events endpoint rather than introducing a duplicate one.
    events.value = (await fetchAdminEvents(1, 100)).items
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Accounting</h1>
        <p class="ds-intro">Select an event to see its financial overview, or open the general accounts.</p>
      </div>

      <hr class="ds-section-line" />

      <router-link to="/admin/accounting/general" class="ds-card ds-card-interactive general-book-card" style="display: block; max-width: 520px">
        <p class="ds-card-title">General accounts</p>
        <p class="ds-meta" style="margin-top: 4px">Costs that belong to no event, and gifts and membership payments.</p>
      </router-link>

      <div class="ds-toolbar">
        <FilterPills v-model="phaseFilter" :options="phaseFilters" label="Filter by event status" />
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Search by event title…" aria-label="Search events" />
      </div>

      <BaseLoadingState v-if="loading" label="Loading events…" />
      <div v-else-if="error" class="ds-alert ds-alert-danger"><div>Couldn't load events. Please try again shortly.</div></div>
      <BaseEmptyState v-else-if="events.length === 0" title="No events yet" description="Create an event first to track its accounting." />
      <BaseEmptyState
        v-else-if="filteredEvents.length === 0"
        title="No matching events"
        description="Try a different filter or search term."
      />
      <div v-else style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
        <section v-for="group in groupedByYear" :key="group.year" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <h2 class="ds-title">{{ group.year }}</h2>
          <div class="ds-cards ds-cards--fill">
            <router-link
              v-for="event in group.items"
              :key="event.id"
              :to="`/admin/accounting/${event.id}`"
              class="ds-card ds-card-interactive"
              :class="{ 'event-card-draft': eventPhase(event) === 'draft' }"
            >
              <div class="event-card-head">
                <p class="ds-card-title">{{ event.title }}</p>
                <span class="ds-badge event-phase" :class="EVENT_PHASE_BADGE[eventPhase(event)]">{{ EVENT_PHASE_LABEL[eventPhase(event)] }}</span>
              </div>
              <p class="ds-meta" style="margin-top: 4px">{{ formatEventDate(event.start_datetime) }}</p>
            </router-link>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.event-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-3); }
.event-phase { flex-shrink: 0; }

/* A draft event is not public yet: dashed edge, a calmer ground and a faint diagonal DRAFT watermark
   behind the text, so it reads differently from live/expired events at a glance. */
.event-card-draft {
  position: relative;
  overflow: hidden;
  border-style: dashed;
  border-color: var(--ds-border-primary);
  background: var(--ds-surface-sunken);
}
.event-card-draft::after {
  content: 'DRAFT';
  position: absolute;
  top: 50%;
  left: 50%;
  font: 800 46px / 1 var(--ds-font-body);
  letter-spacing: 0.18em;
  white-space: nowrap;
  color: var(--ds-text-primary);
  opacity: 0.11;
  transform: translate(-50%, -50%) rotate(-12deg);
  pointer-events: none;
  user-select: none;
}
.event-card-draft > * { position: relative; z-index: 1; }
</style>
