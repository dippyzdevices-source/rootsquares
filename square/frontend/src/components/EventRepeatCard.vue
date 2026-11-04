<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import BaseSelect from './ui/BaseSelect.vue'
import BaseModal from './ui/BaseModal.vue'
import {
  fetchEventSeries,
  repeatEvent,
  updateFollowingEvents,
  endEventSeries,
  SeriesValidationError,
  type EventSeries,
  type SeriesFrequency,
} from '../services/eventSeriesApi'
import { formatDateTime } from '../utils/date'
import { featureEnabled, GROVE_NOTE } from '../services/features'
import UpgradeLink from './UpgradeLink.vue'
import { useToast } from '../composables/useToast'

// "Repeat this event" (wave 14 item 6). Fill the event in once, then make it repeat: every week, every few weeks, or the first/last weekday of the month.
// The following events are ordinary events (own page, tickets, check-in). They are made a few months ahead and topped up by themselves.
const props = defineProps<{ eventId: number }>()
const unlocked = featureEnabled('repeating_events')
const toast = useToast()

const series = ref<EventSeries | null>(null)
const loading = ref(true)
const busy = ref(false)

async function load() {
  loading.value = true
  try {
    series.value = (await fetchEventSeries(props.eventId)).series
  } catch {
    series.value = null
  } finally {
    loading.value = false
  }
}
onMounted(load)

const upcoming = computed(() => (series.value?.occurrences ?? []).filter((o) => new Date(o.start_datetime) >= new Date() && o.status !== 'cancelled'))
const cancelled = computed(() => (series.value?.occurrences ?? []).filter((o) => o.status === 'cancelled').length)

// ---- make it repeat
const modalOpen = ref(false)
const form = ref({ frequency: 'weekly' as SeriesFrequency, interval_weeks: 1, nth: 1, endsBy: 'never' as 'never' | 'date' | 'count', until_date: '', max_count: 10 })
const errors = ref<Record<string, string>>({})
const frequencyChoices = [
  { value: 'weekly', label: 'Every week (or every few weeks)' },
  { value: 'monthly_weekday', label: 'Once a month, on the same weekday' },
]
const nthChoices = [
  { value: '1', label: 'The first' },
  { value: '2', label: 'The second' },
  { value: '3', label: 'The third' },
  { value: '4', label: 'The fourth' },
  { value: '5', label: 'The last' },
]
const endChoices = [
  { value: 'never', label: 'It goes on until I stop it' },
  { value: 'date', label: 'Until a date' },
  { value: 'count', label: 'For a number of times' },
]

async function make() {
  busy.value = true
  errors.value = {}
  try {
    const f = form.value
    const rule = {
      frequency: f.frequency,
      ...(f.frequency === 'weekly' ? { interval_weeks: Number(f.interval_weeks) } : { nth: Number(f.nth) }),
      until_date: f.endsBy === 'date' ? f.until_date || null : null,
      max_count: f.endsBy === 'count' ? Number(f.max_count) : null,
    }
    const result = await repeatEvent(props.eventId, rule)
    series.value = result.series
    modalOpen.value = false
    toast.success(`${result.created} more events made`)
  } catch (e) {
    if (e instanceof SeriesValidationError) errors.value = e.errors
    else toast.error(e instanceof Error ? e.message : 'Could not make this event repeat')
  } finally {
    busy.value = false
  }
}

// ---- keep the series in step, or stop it
async function updateFollowing() {
  busy.value = true
  try {
    const r = await updateFollowingEvents(props.eventId)
    toast.success(`${r.updated} following events updated${r.skipped_with_orders ? `; ${r.skipped_with_orders} left alone because tickets were sold` : ''}`)
    await load()
  } catch (e) {
    toast.error(e instanceof Error ? e.message : 'Could not update the following events')
  } finally {
    busy.value = false
  }
}

const endOpen = ref(false)
async function endHere() {
  busy.value = true
  try {
    const r = await endEventSeries(props.eventId)
    endOpen.value = false
    toast.success(`Stopped. ${r.removed} later events removed${r.cancelled ? `, ${r.cancelled} marked cancelled because tickets were sold` : ''}`)
    await load()
  } catch (e) {
    toast.error(e instanceof Error ? e.message : 'Could not stop the series')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section v-if="!loading" class="ds-card event-repeat-card" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
    <h2 class="ds-title">Repeats</h2>

    <template v-if="!series">
      <p class="ds-meta">This event happens once. If it comes back on a pattern, such as every Sunday, fill it in once and let it repeat.</p>
      <div><BaseButton type="button" variant="secondary" size="sm" class="make-repeat" :disabled="!unlocked" @click="modalOpen = true">Make this event repeat…</BaseButton></div>
      <p v-if="!unlocked" class="ds-caption feature-locked">{{ GROVE_NOTE }}</p>
      <UpgradeLink v-if="!unlocked" />
    </template>

    <template v-else>
      <p class="ds-body"><strong>{{ series.label }}</strong><span v-if="series.ended" class="ds-badge ds-badge-neutral" style="margin-left: var(--ds-space-2)">Stopped</span></p>
      <p class="ds-meta">
        {{ upcoming.length }} coming up<span v-if="cancelled">, {{ cancelled }} cancelled</span>. Each one is an ordinary event you can open and change on its own.
      </p>
      <ul v-if="upcoming.length" style="margin: 0; padding-left: var(--ds-space-5)">
        <li v-for="o in upcoming.slice(0, 6)" :key="o.id">
          <router-link :to="`/admin/events/${o.id}`">{{ formatDateTime(o.start_datetime) }}</router-link>
          <span v-if="o.has_orders" class="ds-meta"> · tickets sold</span>
        </li>
        <li v-if="upcoming.length > 6" class="ds-meta">and {{ upcoming.length - 6 }} more</li>
      </ul>
      <p v-if="!unlocked" class="ds-caption feature-locked">{{ GROVE_NOTE }}</p>
      <div v-if="!series.ended && unlocked" style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
        <BaseButton type="button" variant="secondary" size="sm" class="update-following" :disabled="busy" @click="updateFollowing">Copy this event's wording to the following events</BaseButton>
        <BaseButton type="button" variant="ghost" size="sm" class="end-series" :disabled="busy" @click="endOpen = true">Stop repeating after this one…</BaseButton>
      </div>
      <p v-if="!series.ended && unlocked" class="ds-caption">Copying changes the title, texts, place, limits and time of day of the following events that have no tickets sold. Dates stay.</p>
    </template>

    <BaseModal v-model="modalOpen" title="Make this event repeat">
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <div class="ds-field">
          <span class="ds-field-label">How often</span>
          <BaseSelect v-model="form.frequency" :options="frequencyChoices" aria-label="How often" />
          <span v-if="errors.frequency" class="ds-field-error-text">{{ errors.frequency }}</span>
        </div>
        <label v-if="form.frequency === 'weekly'" class="ds-field">
          <span class="ds-field-label">Every how many weeks</span>
          <span class="ds-field-control"><input v-model="form.interval_weeks" type="number" min="1" max="8" class="ds-field-input repeat-interval" /></span>
          <span v-if="errors.interval_weeks" class="ds-field-error-text">{{ errors.interval_weeks }}</span>
        </label>
        <div v-else class="ds-field">
          <span class="ds-field-label">Which one</span>
          <BaseSelect :model-value="String(form.nth)" :options="nthChoices" aria-label="Which weekday of the month" @update:model-value="(v) => (form.nth = Number(v))" />
          <span v-if="errors.nth" class="ds-field-error-text">{{ errors.nth }}</span>
        </div>
        <p class="ds-caption">It keeps this event's weekday and time of day.</p>
        <div class="ds-field">
          <span class="ds-field-label">Until when</span>
          <BaseSelect v-model="form.endsBy" :options="endChoices" aria-label="Until when" />
        </div>
        <label v-if="form.endsBy === 'date'" class="ds-field">
          <span class="ds-field-label">Last day</span>
          <span class="ds-field-control"><input v-model="form.until_date" type="date" class="ds-field-input repeat-until" /></span>
          <span v-if="errors.until_date" class="ds-field-error-text">{{ errors.until_date }}</span>
        </label>
        <label v-if="form.endsBy === 'count'" class="ds-field">
          <span class="ds-field-label">Number of times (including this one)</span>
          <span class="ds-field-control"><input v-model="form.max_count" type="number" min="2" max="520" class="ds-field-input repeat-count" /></span>
          <span v-if="errors.max_count" class="ds-field-error-text">{{ errors.max_count }}</span>
        </label>
        <p class="ds-caption">The next months are made now, and more are added by themselves as time goes by. Ticket types and the schedule are copied to each one.</p>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" @click="modalOpen = false">Cancel</BaseButton>
          <BaseButton type="button" variant="primary" class="confirm-repeat" :disabled="busy" @click="make">Make it repeat</BaseButton>
        </div>
      </div>
    </BaseModal>

    <BaseModal v-model="endOpen" title="Stop repeating after this event?">
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-body">The later events are removed. A later event that already has tickets sold is kept and marked cancelled, so nobody is forgotten.</p>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" @click="endOpen = false">Keep repeating</BaseButton>
          <BaseButton type="button" variant="danger" class="confirm-end" :disabled="busy" @click="endHere">Stop repeating</BaseButton>
        </div>
      </div>
    </BaseModal>
  </section>
</template>
