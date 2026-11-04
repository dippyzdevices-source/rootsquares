<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import FilterPills from '../../components/ui/FilterPills.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { PAGE_SIZE } from '../../composables/useClientPagination'
import BaseModal from '../../components/ui/BaseModal.vue'
import {
  fetchAdminUsers,
  updateAdminUserRole,
  fetchAdminUserEvents,
  setAdminUserEvents,
  type AdminUserRecord,
  type AssignableEvent,
} from '../../services/adminUsersApi'
import { formatEventDate } from '../../utils/date'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: userRoleLabel } = useLookup('user_role')
const toast = useToast()
const users = ref<AdminUserRecord[]>([])
const loading = ref(true)
const search = ref('')
const roleFilter = ref('all')
const roleOptions = [
  { value: 'all', label: 'All' },
  { value: 'volunteer', label: 'Volunteers' },
  { value: 'member', label: 'Members' },
]
const updating = ref<number | null>(null)

const assignModalOpen = ref(false)
const assigningUser = ref<AdminUserRecord | null>(null)
const assignableEvents = ref<AssignableEvent[]>([])
const selectedEventIds = ref<number[]>([])
const loadingEvents = ref(false)
const savingEvents = ref(false)

const page = ref(1)
const totalPages = ref(1)
const total = ref(0)

// Filter/search changes go back to page 1 (the page watcher does the load when it moves).
function reload() {
  if (page.value !== 1) page.value = 1
  else load()
}

async function load() {
  loading.value = true
  try {
    const data = await fetchAdminUsers(search.value || undefined, roleFilter.value === 'all' ? undefined : roleFilter.value, PAGE_SIZE, page.value)
    users.value = data.items
    totalPages.value = data.total_pages
    total.value = data.total
  } catch {
    toast.error('Could not load users')
  } finally {
    loading.value = false
  }
}

async function toggleRole(user: AdminUserRecord) {
  updating.value = user.id
  const newRole = user.role === 'volunteer' ? 'member' : 'volunteer'
  try {
    await updateAdminUserRole(user.id, newRole)
    toast.success(`${user.email} is now a ${newRole}`)
    await load()
  } catch {
    toast.error("Could not update this user's role")
  } finally {
    updating.value = null
  }
}

function toggleEvent(id: number) {
  if (selectedEventIds.value.includes(id)) {
    selectedEventIds.value = selectedEventIds.value.filter((existing) => existing !== id)
  } else {
    selectedEventIds.value = [...selectedEventIds.value, id]
  }
}

async function openAssignEvents(user: AdminUserRecord) {
  assigningUser.value = user
  assignModalOpen.value = true
  loadingEvents.value = true
  try {
    const { events, assigned_event_ids } = await fetchAdminUserEvents(user.id)
    assignableEvents.value = events
    selectedEventIds.value = assigned_event_ids
  } catch {
    toast.error("Could not load this volunteer's events")
    assignModalOpen.value = false
  } finally {
    loadingEvents.value = false
  }
}

async function saveAssignedEvents() {
  if (!assigningUser.value) return
  savingEvents.value = true
  try {
    await setAdminUserEvents(assigningUser.value.id, selectedEventIds.value)
    toast.success('Assigned events updated')
    assignModalOpen.value = false
  } catch {
    toast.error("Could not update this volunteer's events")
  } finally {
    savingEvents.value = false
  }
}

watch(roleFilter, reload)
watch(page, load)
onMounted(load)
</script>

<template>
  <div class="ds-scope" style="max-width: 800px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div class="ds-heading">
      <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
      <h1 class="ds-display ds-display-s">Volunteers</h1>
      <p class="ds-meta">
        Give a member door check-in access without making them an admin — admin roles can only be
        granted from the command line.
      </p>
    </div>

    <hr class="ds-section-line" />

    <div class="ds-toolbar">
      <FilterPills v-model="roleFilter" :options="roleOptions" label="Filter people by role" />
      <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Search by name or email…" aria-label="Search by name or email" @keyup.enter="reload" />
    </div>

    <BaseLoadingState v-if="loading" label="Loading users…" />
    <BaseEmptyState
      v-else-if="users.length === 0"
      title="No matching user found"
      description="This only searches people who have logged in before (and aren't admins) — a member who hasn't logged in yet, or an admin account, won't appear here."
    />
    <div v-else class="ds-table-wrap">
      <div class="ds-table-scroll">
        <table class="ds-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td data-emphasis>{{ user.member_name ?? '—' }}</td>
              <td>{{ user.email }}</td>
              <td><span class="ds-badge" :class="user.role === 'volunteer' ? 'ds-badge-success' : 'ds-badge-neutral'">{{ userRoleLabel(user.role) }}</span></td>
              <td data-align="right">
                <div style="display: flex; justify-content: flex-end; align-items: center; gap: var(--ds-space-1)">
                  <BaseIconButton variant="bare"
                    v-if="user.role === 'volunteer'"
                    size="sm"
                    :label="`Assign Check-in access to ${user.member_name ?? user.email} `"
                    @click="openAssignEvents(user)"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2" /><line x1="16" x2="16" y1="2" y2="6" /><line x1="8" x2="8" y1="2" y2="6" /><line x1="3" x2="21" y1="10" y2="10" /></svg>
                  </BaseIconButton>
                  <BaseIconButton
                    size="sm"
                    :variant="user.role === 'volunteer' ? 'danger' : 'success'"
                    :label="user.role === 'volunteer' ? `Revert ${user.member_name ?? user.email} to member` : `Make ${user.member_name ?? user.email} a volunteer`"
                    :disabled="updating === user.id"
                    @click="toggleRole(user)"
                  >
                    <svg v-if="user.role === 'volunteer'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><line x1="22" x2="16" y1="11" y2="11" /></svg>
                    <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><polyline points="16 11 18 13 22 9" /></svg>
                  </BaseIconButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />

    <BaseModal
      v-model="assignModalOpen"
      size="lg"
      :title="assigningUser ? `Check-in access — ${assigningUser.member_name ?? assigningUser.email}` : 'Check-in access'"
    >
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-meta">
          Choose which events this volunteer can scan tickets for at the door. This is
          separate from being assigned to help with an event — manage that from the
          event's own edit page.
        </p>
        <BaseLoadingState v-if="loadingEvents" label="Loading events…" />
        <BaseEmptyState
          v-else-if="assignableEvents.length === 0"
          title="No events yet"
          description="Create an event first, then come back here to assign this volunteer to it."
        />
        <template v-else>
          <div style="max-height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: var(--ds-space-2); padding: 2px">
            <label
              v-for="event in assignableEvents"
              :key="event.id"
              class="ds-checkbox"
              style="padding: var(--ds-space-3) var(--ds-space-4); border-radius: var(--ds-radius-md); border: 1px solid var(--ds-border-hairline); transition: border-color 140ms var(--ds-ease), background-color 140ms var(--ds-ease)"
              :style="selectedEventIds.includes(event.id) ? 'border-color: var(--ds-border-primary); background: var(--ds-action-ghost-hover)' : ''"
            >
              <input
                type="checkbox"
                :checked="selectedEventIds.includes(event.id)"
                @change="toggleEvent(event.id)"
              />
              <span class="ds-checkbox-box">✓</span>
              <span style="flex: 1; min-width: 0">
                <span class="ds-checkbox-label" style="font-weight: 600">{{ event.title }}</span>
                <span class="ds-checkbox-desc">{{ formatEventDate(event.start_datetime) }}</span>
              </span>
            </label>
          </div>
          <p class="ds-caption">{{ selectedEventIds.length }} of {{ assignableEvents.length }} selected</p>
        </template>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" @click="assignModalOpen = false">Cancel</BaseButton>
          <BaseButton
            type="button"
            :disabled="savingEvents || loadingEvents"
            @click="saveAssignedEvents"
          >
            {{ savingEvents ? 'Saving…' : 'Save' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
