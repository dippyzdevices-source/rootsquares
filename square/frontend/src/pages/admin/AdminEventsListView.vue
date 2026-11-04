<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import FilterPills from '../../components/ui/FilterPills.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { eventPhase, EVENT_PHASE_BADGE, EVENT_PHASE_LABEL, type EventPhase } from '../../utils/eventPhase'
import { useClientPagination } from '../../composables/useClientPagination'
import BaseModal from '../../components/ui/BaseModal.vue'
import {
  deleteAdminEvent,
  duplicateAdminEvent,
  fetchAdminEvents,
  type AdminEvent,
} from '../../services/adminEventsApi'
import { formatEventDate } from '../../utils/date'
import { useLookup } from '../../composables/useLookup'
import { useToast } from '../../composables/useToast'
import { squareProfile } from '../../services/squareConfig'

const router = useRouter()
const events = ref<AdminEvent[]>([])
const loading = ref(true)
const error = ref(false)
const deleteTarget = ref<AdminEvent | null>(null)
const duplicating = ref<number | null>(null)
const toast = useToast()
// An Event pass holds one event (ADR 044): once it has one, the new-event button gives way to a note.
const passFull = computed(() => squareProfile.eventPass !== null && events.value.length >= 1)
const { label: eventTypeLabel } = useLookup('event_type')

// Same Draft / Live / Expired vocabulary as the Accounting events page (utils/eventPhase.ts).
const filters: { value: 'all' | EventPhase; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'live', label: 'Live' },
  { value: 'draft', label: 'Draft' },
  { value: 'expired', label: 'Expired' },
]
const activeFilter = ref<'all' | EventPhase>('all')

const search = ref('')

const filteredEvents = computed(() => {
  const q = search.value.trim().toLowerCase()
  return events.value.filter(
    (event) =>
      (activeFilter.value === 'all' || eventPhase(event) === activeFilter.value) &&
      (!q || event.title.toLowerCase().includes(q)),
  )
})

const { page, totalPages, pageItems, total } = useClientPagination(filteredEvents)
watch([activeFilter, search], () => (page.value = 1))

async function load() {
  loading.value = true
  error.value = false
  try {
    const data = await fetchAdminEvents(1, 50)
    events.value = data.items
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function duplicate(event: AdminEvent) {
  duplicating.value = event.id
  try {
    const copy = await duplicateAdminEvent(event.id)
    toast.success('Event duplicated — update the details before publishing')
    router.push(`/admin/events/${copy.id}/edit`)
  } catch {
    toast.error('Could not duplicate this event')
  } finally {
    duplicating.value = null
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await deleteAdminEvent(deleteTarget.value.id)
    toast.success('Event deleted')
    deleteTarget.value = null
    await load()
  } catch {
    toast.error('Could not delete event')
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">Events</h1>
        </div>
        <p v-if="passFull" class="ds-meta" data-testid="pass-one-event">An Event pass holds one event (one day or consecutive days).</p>
        <BaseButton v-else to="/admin/events/new" variant="secondary" size="sm">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
          New event
        </BaseButton>
      </div>

      <hr class="ds-section-line" />

      <BaseLoadingState v-if="loading" label="Loading events…" />
      <BaseEmptyState v-else-if="error" title="Couldn't load events" description="Please try again shortly." />
      <BaseEmptyState v-else-if="events.length === 0" title="No events yet" description="Create your first event to get started." />
      <template v-else>
        <div class="ds-toolbar">
          <FilterPills v-model="activeFilter" :options="filters" label="Filter by event status" />
          <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Search by event title…" aria-label="Search events" />
        </div>

        <div v-if="filteredEvents.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
          <p class="ds-meta">No events match this filter or search.</p>
        </div>
        <div v-else class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table">
              <caption>{{ filteredEvents.length }} of {{ events.length }} events</caption>
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Type</th>
                  <th>Start</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="event in pageItems" :key="event.id">
                  <td data-emphasis>{{ event.title }}</td>
                  <td><span class="ds-badge ds-badge-neutral">{{ eventTypeLabel(event.event_type) }}</span></td>
                  <td>{{ formatEventDate(event.start_datetime) }}</td>
                  <td>
                    <span class="ds-badge event-phase" :class="EVENT_PHASE_BADGE[eventPhase(event)]">{{ EVENT_PHASE_LABEL[eventPhase(event)] }}</span>
                  </td>
                  <td data-align="right">
                    <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                      <BaseIconButton variant="bare" :to="`/admin/events/${event.id}/edit`" size="sm" :label="`Edit ${event.title}`">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                      </BaseIconButton>
                      <BaseIconButton variant="bare" size="sm" :label="`Duplicate ${event.title}`" :disabled="duplicating === event.id" @click="duplicate(event)">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" /></svg>
                      </BaseIconButton>
                      <BaseIconButton variant="danger" size="sm" :label="`Delete ${event.title}`" @click="deleteTarget = event">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                      </BaseIconButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />
      </template>
    </div>

    <BaseModal
      :model-value="!!deleteTarget"
      title="Delete event"
      @update:model-value="deleteTarget = null"
    >
      <p class="ds-body">Delete "{{ deleteTarget?.title }}"? This cannot be undone.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" size="md" @click="deleteTarget = null">Cancel</BaseButton>
        <BaseButton type="button" variant="danger" size="md" @click="confirmDelete">Delete</BaseButton>
      </div>
    </BaseModal>
  </div>
</template>
