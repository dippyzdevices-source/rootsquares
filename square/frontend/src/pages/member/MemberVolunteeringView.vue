<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchMyTaskAssignments, type MyTaskAssignment } from '../../services/memberApi'
import { formatEventDate } from '../../utils/date'
import { useLookup } from '../../composables/useLookup'

const { label: taskCategoryLabel } = useLookup('task_category')
const loading = ref(true)
const error = ref(false)
const assignments = ref<MyTaskAssignment[]>([])

// Matches the same "has it started yet" rule the backend uses for events elsewhere in the
// app — an event with no end date is only "past" once its start time has gone by.
function isUpcoming(assignment: MyTaskAssignment): boolean {
  const reference = assignment.event_end_datetime ?? assignment.event_start_datetime
  return new Date(reference) >= new Date()
}

const upcoming = computed(() =>
  assignments.value
    .filter(isUpcoming)
    .sort((a, b) => new Date(a.event_start_datetime).getTime() - new Date(b.event_start_datetime).getTime()),
)

const past = computed(() =>
  assignments.value
    .filter((a) => !isUpcoming(a))
    .sort((a, b) => new Date(b.event_start_datetime).getTime() - new Date(a.event_start_datetime).getTime()),
)

onMounted(async () => {
  try {
    assignments.value = await fetchMyTaskAssignments()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="ds-scope">
    <div style="max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />My portal</span>
        <h1 class="ds-display ds-display-s">Volunteering</h1>
        <p class="ds-intro">Every event you've been asked to help with — upcoming and past.</p>
      </div>

      <BaseLoadingState v-if="loading" label="Loading your volunteering history…" />
      <BaseEmptyState
        v-else-if="error"
        title="Couldn't load your volunteering history"
        description="Please try again shortly."
      />
      <BaseEmptyState
        v-else-if="assignments.length === 0"
        title="No volunteering assigned yet"
        description="When an admin assigns you to help with an event, it will show up here."
      />
      <template v-else>
        <section style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <h2 class="ds-title">Upcoming</h2>
          <BaseEmptyState
            v-if="upcoming.length === 0"
            title="No upcoming volunteering"
            description="You're not currently assigned to help with any upcoming events."
          />
          <div v-else style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
            <div v-for="assignment in upcoming" :key="assignment.id" class="ds-card" style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-3); flex-wrap: wrap">
              <div>
                <router-link :to="`/events/${assignment.event_slug}`" class="ds-body" style="font-weight: 600; color: var(--ds-text-heading)">
                  {{ assignment.event_title }}
                </router-link>
                <p class="ds-caption" style="margin-top: 2px">{{ formatEventDate(assignment.event_start_datetime) }}</p>
              </div>
              <span class="ds-badge ds-badge-accent">{{ taskCategoryLabel(assignment.category) }}</span>
            </div>
          </div>
        </section>

        <section style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <h2 class="ds-title">Past</h2>
          <BaseEmptyState
            v-if="past.length === 0"
            title="No past volunteering"
            description="Events you've already helped with will show up here afterward."
          />
          <div v-else style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
            <div v-for="assignment in past" :key="assignment.id" class="ds-card ds-card-sunken" style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-3); flex-wrap: wrap">
              <div>
                <router-link :to="`/events/${assignment.event_slug}`" class="ds-body" style="font-weight: 600; color: var(--ds-text-heading)">
                  {{ assignment.event_title }}
                </router-link>
                <p class="ds-caption" style="margin-top: 2px">{{ formatEventDate(assignment.event_start_datetime) }}</p>
              </div>
              <span class="ds-badge ds-badge-neutral">{{ taskCategoryLabel(assignment.category) }}</span>
            </div>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>
