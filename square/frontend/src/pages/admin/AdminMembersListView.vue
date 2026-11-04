<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import MemberSectionNav from '../../components/MemberSectionNav.vue'
import BaseMultiSelect from '../../components/ui/BaseMultiSelect.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { fetchAdminMembershipTypes } from '../../services/adminMembershipTypesApi'
import { PAGE_SIZE } from '../../composables/useClientPagination'
import { fetchAdminMembers, exportMembers, resendMemberWelcomeEmail, addAdminMember, DuplicateMemberError, ValidationError, type AdminMemberSummary } from '../../services/adminMembersApi'
import { moduleEnabled } from '../../services/modules'
import { updateAdminMembership } from '../../services/adminMembershipsApi'
import { downloadBlob } from '../../utils/download'
import { humanize } from '../../utils/formatEnum'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: membershipStatusLabel } = useLookup('membership_status')
// Without the Memberships module this is a plain list of people (ADR 044): no membership column, filters or approve button.
const membershipsOn = moduleEnabled('memberships')
const noun = membershipsOn ? 'Members' : 'People'
const toast = useToast()
const route = useRoute()
const router = useRouter() as ReturnType<typeof useRouter> | undefined

// Tapping anywhere on a row opens the member; the Approve/eye controls keep their own click.
function openMember(event: MouseEvent, member: AdminMemberSummary) {
  if ((event.target as HTMLElement).closest('a, button')) return
  void router?.push(`/admin/members/${member.id}`)
}

const statusOptions = computed(() => [
  { value: 'pending', label: membershipStatusLabel('pending') },
  { value: 'active', label: membershipStatusLabel('active') },
  { value: 'expired', label: membershipStatusLabel('expired') },
  { value: 'cancelled', label: membershipStatusLabel('cancelled') },
  { value: 'suspended', label: membershipStatusLabel('suspended') },
])
// Pre-selects the filter from `?status=` (e.g. the dashboard's "Review requests" link).
const initialStatuses = (typeof route.query.status === 'string' ? route.query.status : '').split(',')
const status = ref<string[]>(initialStatuses.filter((s) => statusOptions.value.some((opt) => opt.value === s)))
const approving = ref<number | null>(null)

const members = ref<AdminMemberSummary[]>([])
const page = ref(1)
const totalPages = ref(1)
const total = ref(0)
const loading = ref(true)
const error = ref(false)
const query = ref('')
const membershipType = ref<string[]>([])
const typeOptions = ref<{ value: string; label: string }[]>([])
const exporting = ref(false)

function membershipBadgeTone(status: string): string {
  if (status === 'active') return 'ds-badge-success'
  if (status === 'expired' || status === 'cancelled' || status === 'suspended') return 'ds-badge-danger'
  return 'ds-badge-neutral'
}

async function load() {
  loading.value = true
  error.value = false
  try {
    const data = await fetchAdminMembers(query.value, '', PAGE_SIZE, status.value, page.value, membershipType.value)
    members.value = data.items
    totalPages.value = data.total_pages
    total.value = data.total
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

// Add a person by hand (a volunteer, a helper): no membership is created.
const addOpen = ref(false)
const adding = ref(false)
const newPerson = ref({ name: '', email: '', phone: '' })
const addErrors = ref<Record<string, string>>({})

function openAdd() {
  newPerson.value = { name: '', email: '', phone: '' }
  addErrors.value = {}
  addOpen.value = true
}

async function submitAdd() {
  adding.value = true
  addErrors.value = {}
  try {
    const payload = { name: newPerson.value.name.trim(), email: newPerson.value.email.trim() || undefined, phone: newPerson.value.phone.trim() || undefined }
    await addAdminMember(payload)
    addOpen.value = false
    toast.success('Person added')
    await load()
  } catch (e) {
    if (e instanceof DuplicateMemberError) addErrors.value = { email: 'This email is already on the list.' }
    else if (e instanceof ValidationError) addErrors.value = e.errors
    else toast.error('Could not add this person')
  } finally {
    adding.value = false
  }
}

async function handleExport() {
  exporting.value = true
  try {
    const blob = await exportMembers({ q: query.value, status: status.value, membershipType: membershipType.value })
    downloadBlob(blob, 'members.xlsx')
  } catch {
    toast.error('Could not export members')
  } finally {
    exporting.value = false
  }
}

const sendingWelcome = ref<number | null>(null)

// The automatic welcome email goes out once, at first sign-in - this sends it again (to a member who has
// an email address, whether or not they have ever signed in).
async function resendWelcome(member: AdminMemberSummary) {
  sendingWelcome.value = member.id
  try {
    await resendMemberWelcomeEmail(member.id)
    toast.success(`Welcome email sent to ${member.email}`)
  } catch {
    toast.error('Could not send the welcome email. Please try again shortly.')
  } finally {
    sendingWelcome.value = null
  }
}

async function approve(member: AdminMemberSummary) {
  if (!member.latest_membership) return
  approving.value = member.latest_membership.id
  try {
    await updateAdminMembership(member.latest_membership.id, { status: 'active' })
    toast.success('Membership approved')
    await load()
  } catch {
    toast.error('Could not approve this membership')
  } finally {
    approving.value = null
  }
}

// Filter/search changes go back to page 1 (the page watcher does the load when it moves).
function reload() {
  if (page.value !== 1) page.value = 1
  else load()
}

watch([status, membershipType], reload)
watch(page, load)
async function loadTypeOptions() {
  try {
    const { items } = await fetchAdminMembershipTypes()
    typeOptions.value = items.map((t) => ({ value: t.name, label: humanize(t.name) }))
  } catch {
    /* leave the options empty */
  }
}

onMounted(() => {
  if (membershipsOn) void loadTypeOptions()
  void load()
})
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">{{ noun }}</h1>
        </div>
        <div style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
        <BaseButton size="sm" type="button" class="add-person" @click="openAdd">Add person</BaseButton>
        <BaseButton size="sm" type="button" variant="secondary" class="export-members" :disabled="exporting" @click="handleExport">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
          {{ exporting ? 'Exporting…' : 'Export to Excel' }}
        </BaseButton>
        </div>
        </div>

      <MemberSectionNav />

      <div class="ds-toolbar">
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="query" placeholder="Search by name or email" @keyup.enter="reload" />
        <BaseMultiSelect v-if="membershipsOn" size="sm" class="ds-toolbar-select-wide" v-model="membershipType" :options="typeOptions" all-label="All types" aria-label="Filter by membership type" highlight-active />
        <BaseMultiSelect v-if="membershipsOn" size="sm" class="ds-toolbar-select-wide" v-model="status" :options="statusOptions" all-label="All statuses" aria-label="Filter by membership status" highlight-active />
      </div>

      <BaseLoadingState v-if="loading" :label="`Loading ${noun.toLowerCase()}…`" />
      <BaseEmptyState v-else-if="error" title="Couldn't load members" description="Please try again shortly." />
      <BaseEmptyState
        v-else-if="members.length === 0"
        :title="`No ${noun.toLowerCase()} found`"
        :description="membershipsOn ? 'Members appear here once they log in and create a profile, or after an Excel import.' : 'People appear here once you add them or they sign in and create a profile.'"
      />
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>{{ membershipsOn ? 'Member' : 'Person' }}</th>
                <th>Email</th>
                <th v-if="membershipsOn">Membership</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="member in members" :key="member.id" class="ds-row-clickable" @click="openMember($event, member)">
                <td data-emphasis>
                  <span style="display: inline-flex; align-items: center; gap: var(--ds-space-3)">
                    <BaseAvatar :name="member.name" size="sm" />
                    {{ member.name }}
                  </span>
                </td>
                <td>{{ member.email }}</td>
                <td v-if="membershipsOn">
                  <span v-if="member.latest_membership" class="ds-badge" :class="membershipBadgeTone(member.latest_membership.status)">
                    {{ humanize(member.latest_membership.membership_type) }} —
                    {{ member.latest_membership.awaiting_payment ? 'Awaiting payment' : membershipStatusLabel(member.latest_membership.status) }}
                  </span>
                  <span v-else class="ds-meta">No membership yet</span>
                </td>
                <td data-align="right">
                  <!-- Every row action is a 32px icon button with a tooltip (design system admin toolbar pattern). -->
                  <div class="member-row-actions">
                    <BaseIconButton
                      v-if="membershipsOn && member.latest_membership?.status === 'pending' && !member.latest_membership.awaiting_payment"
                      variant="success"
                      size="sm"
                      class="approve-membership"
                      :label="`Approve ${member.name}`"
                      :disabled="approving === member.latest_membership.id"
                      @click="approve(member)"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
                    </BaseIconButton>
                    <BaseIconButton
                      v-if="member.email"
                      variant="bare"
                      size="sm"
                      class="resend-welcome"
                      :label="`Resend welcome email to ${member.name}`"
                      :disabled="sendingWelcome === member.id"
                      @click="resendWelcome(member)"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 7-10 6L2 7" /></svg>
                    </BaseIconButton>
                    <BaseIconButton variant="bare" :to="`/admin/members/${member.id}`" size="sm" class="view-member" :label="`View ${member.name}`">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" /><circle cx="12" cy="12" r="3" /></svg>
                    </BaseIconButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />
    </div>
    <BaseModal v-model="addOpen" title="Add person">
      <form style="display: flex; flex-direction: column; gap: var(--ds-space-4)" @submit.prevent="submitAdd">
        <label class="ds-field">
          <span class="ds-field-label">Name</span>
          <span class="ds-field-control"><input v-model="newPerson.name" type="text" class="ds-field-input" autocomplete="off" /></span>
          <span v-if="addErrors.name" class="ds-field-error-text">{{ addErrors.name }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Email (optional)</span>
          <span class="ds-field-control"><input v-model="newPerson.email" type="email" class="ds-field-input" autocomplete="off" /></span>
          <span v-if="addErrors.email" class="ds-field-error-text">{{ addErrors.email }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Phone (optional)</span>
          <span class="ds-field-control"><input v-model="newPerson.phone" type="tel" class="ds-field-input" autocomplete="off" /></span>
          <span v-if="addErrors.phone" class="ds-field-error-text">{{ addErrors.phone }}</span>
        </label>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="secondary" size="sm" @click="addOpen = false">Cancel</BaseButton>
          <BaseButton type="submit" size="sm" :disabled="adding || !newPerson.name.trim()">{{ adding ? 'Adding…' : 'Add person' }}</BaseButton>
        </div>
      </form>
    </BaseModal>
  </div>
</template>

<style scoped>
.member-row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--ds-space-2);
}
</style>
