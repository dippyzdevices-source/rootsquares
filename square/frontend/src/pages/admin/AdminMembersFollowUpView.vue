<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import BaseAvatarLabel from '../../components/ui/BaseAvatarLabel.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { useClientPagination } from '../../composables/useClientPagination'
import BaseModal from '../../components/ui/BaseModal.vue'
import MemberSectionNav from '../../components/MemberSectionNav.vue'
import {
  fetchFollowUp,
  sendFollowUpReminder,
  removeFollowUpRequest,
  type FollowUpDue,
  type FollowUpRequest,
} from '../../services/adminMembershipFollowUpApi'
import { humanize } from '../../utils/formatEnum'
import { formatPrice } from '../../utils/money'
import { useToast } from '../../composables/useToast'

const toast = useToast()

const requests = ref<FollowUpRequest[]>([])
const dues = ref<FollowUpDue[]>([])
const search = ref('')
function matches(row: { name: string; email: string | null }): boolean {
  const q = search.value.trim().toLowerCase()
  return !q || row.name.toLowerCase().includes(q) || (row.email ?? '').toLowerCase().includes(q)
}
const visibleRequests = computed(() => requests.value.filter(matches))
const visibleDues = computed(() => dues.value.filter(matches))
const { page: reqPageNo, totalPages: reqTotalPages, pageItems: requestItems, total: reqTotal } = useClientPagination(visibleRequests)
const { page: duePageNo, totalPages: dueTotalPages, pageItems: dueItems, total: dueTotal } = useClientPagination(visibleDues)
watch(search, () => {
  reqPageNo.value = 1
  duePageNo.value = 1
})
const loading = ref(true)
const error = ref(false)
const busyId = ref<number | null>(null)
const removeTarget = ref<FollowUpRequest | null>(null)
const removeOpen = ref(false)

function daysText(days: number): string {
  if (days <= 0) return 'Today'
  return days === 1 ? '1 day' : `${days} days`
}

function remindedText(iso: string | null): string {
  if (!iso) return 'Never'
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (days <= 0) return 'Today'
  return days === 1 ? '1 day ago' : `${days} days ago`
}

function reminderTitle(row: { email: string | null; can_remind: boolean }): string {
  if (!row.email) return 'This member has no email address'
  if (!row.can_remind) return 'A reminder went out in the last 3 days'
  return 'Email a payment reminder'
}

async function load() {
  loading.value = true
  error.value = false
  try {
    const data = await fetchFollowUp()
    requests.value = data.requests
    dues.value = data.dues
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function remind(row: FollowUpRequest | FollowUpDue) {
  busyId.value = row.membership_id
  try {
    const result = await sendFollowUpReminder(row.membership_id)
    row.last_reminded_at = result.last_reminded_at
    row.can_remind = false
    toast.success(`Reminder sent to ${row.name}`)
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Could not send the reminder')
  } finally {
    busyId.value = null
  }
}

function askRemove(row: FollowUpRequest) {
  removeTarget.value = row
  removeOpen.value = true
}

async function confirmRemove() {
  const row = removeTarget.value
  if (!row) return
  busyId.value = row.membership_id
  try {
    await removeFollowUpRequest(row.membership_id)
    requests.value = requests.value.filter((r) => r.membership_id !== row.membership_id)
    toast.success('Request removed')
    removeOpen.value = false
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Could not remove the request')
  } finally {
    busyId.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Members</h1>
      </div>

      <MemberSectionNav />

      <p class="ds-meta" style="max-width: 640px">
        People who haven't paid yet. A new request becomes an active membership by itself once its first
        payment is confirmed — a reminder email is the nudge when it doesn't come.
      </p>

      <div class="ds-toolbar">
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Search by name or email…" aria-label="Search unpaid requests and dues" />
      </div>

      <BaseLoadingState v-if="loading" label="Loading…" />
      <BaseEmptyState v-else-if="error" title="Couldn't load this list" description="Please try again shortly." />

      <template v-else>
        <section class="followup-requests fu-section">
          <h2 class="ds-title">New requests <span class="ds-meta">({{ requests.length }})</span></h2>
          <BaseEmptyState
            v-if="requests.length === 0"
            title="No unpaid requests"
            description="Members who ask for a membership and haven't paid yet will show up here."
          />
          <p v-else-if="visibleRequests.length === 0" class="ds-meta">No requests match this search.</p>
          <div v-else class="ds-table-wrap">
            <div class="ds-table-scroll">
              <table class="ds-table fu-table">
                <thead>
                  <tr>
                    <th class="fu-col-who">Member</th>
                    <th>Details</th>
                    <th class="fu-col-actions"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in requestItems" :key="row.membership_id" class="followup-request-row">
                    <td class="fu-who" data-emphasis>
                      <BaseAvatarLabel :name="row.name" :email="row.email">
                        <span v-if="row.phone" class="ds-avatar-label-email">{{ row.phone }}</span>
                      </BaseAvatarLabel>
                    </td>
                    <td class="fu-info">
                      <div class="fu-main">{{ humanize(row.membership_type) }} · {{ formatPrice(row.amount) }}</div>
                      <div class="ds-caption">{{ row.period_label }}</div>
                      <div class="ds-caption">Waiting {{ daysText(row.days_waiting) }} · Reminded {{ remindedText(row.last_reminded_at) }}</div>
                    </td>
                    <td class="fu-actions-cell" data-align="right">
                      <div class="fu-actions">
                        <BaseIconButton
                          variant="info"
                          size="sm"
                          class="send-reminder"
                          :label="`Remind ${row.name}`"
                          :disabled="busyId === row.membership_id || !row.can_remind || !row.email"
                          :title="reminderTitle(row)"
                          @click="remind(row)"
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2" /><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" /></svg>
                        </BaseIconButton>
                        <BaseIconButton variant="bare" :to="`/admin/members/${row.member_id}`" size="sm" class="view-member" :label="`View ${row.name}`">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" /><circle cx="12" cy="12" r="3" /></svg>
                        </BaseIconButton>
                        <BaseIconButton variant="danger" size="sm" class="remove-request" :label="`Remove ${row.name}`" :disabled="busyId === row.membership_id" @click="askRemove(row)">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" /></svg>
                        </BaseIconButton>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <PaginationBar v-model:page="reqPageNo" :total-pages="reqTotalPages" :total="reqTotal" />
          </div>
        </section>

        <section class="followup-dues fu-section">
          <h2 class="ds-title">Active members with payments due <span class="ds-meta">({{ dues.length }})</span></h2>
          <BaseEmptyState
            v-if="dues.length === 0"
            title="Nothing overdue"
            description="Active members with unpaid periods that have started will show up here."
          />
          <p v-else-if="visibleDues.length === 0" class="ds-meta">No members match this search.</p>
          <div v-else class="ds-table-wrap">
            <div class="ds-table-scroll">
              <table class="ds-table fu-table">
                <thead>
                  <tr>
                    <th class="fu-col-who">Member</th>
                    <th>Details</th>
                    <th class="fu-col-actions"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in dueItems" :key="row.membership_id" class="followup-due-row">
                    <td class="fu-who" data-emphasis>
                      <BaseAvatarLabel :name="row.name" :email="row.email">
                        <span v-if="row.phone" class="ds-avatar-label-email">{{ row.phone }}</span>
                      </BaseAvatarLabel>
                    </td>
                    <td class="fu-info">
                      <div class="fu-main">{{ formatPrice(row.due_total) }} due</div>
                      <div class="ds-caption">{{ humanize(row.membership_type) }} · {{ row.due_count }} period{{ row.due_count === 1 ? '' : 's' }}</div>
                      <div class="ds-caption">{{ daysText(row.days_overdue) }} overdue · Reminded {{ remindedText(row.last_reminded_at) }}</div>
                    </td>
                    <td class="fu-actions-cell" data-align="right">
                      <div class="fu-actions">
                        <BaseIconButton
                          variant="info"
                          size="sm"
                          class="send-reminder"
                          :label="`Remind ${row.name}`"
                          :disabled="busyId === row.membership_id || !row.can_remind || !row.email"
                          :title="reminderTitle(row)"
                          @click="remind(row)"
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2" /><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" /></svg>
                        </BaseIconButton>
                        <BaseIconButton variant="bare" :to="`/admin/members/${row.member_id}`" size="sm" class="view-member" :label="`View ${row.name}`">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" /><circle cx="12" cy="12" r="3" /></svg>
                        </BaseIconButton>
                        <span class="fu-slot" aria-hidden="true" />
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <PaginationBar v-model:page="duePageNo" :total-pages="dueTotalPages" :total="dueTotal" />
          </div>
        </section>
      </template>
    </div>

    <BaseModal v-model="removeOpen" title="Remove this request?">
      <div style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-body">
          {{ removeTarget?.name }}'s unpaid {{ humanize(removeTarget?.membership_type ?? '') }} request will be deleted.
          They can always request again.
        </p>
        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton type="button" variant="ghost" size="md" @click="removeOpen = false">Keep it</BaseButton>
          <BaseButton type="button" variant="danger" size="md" class="confirm-remove" :disabled="busyId !== null" @click="confirmRemove">
            Remove request
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </div>
</template>

<style scoped>
.fu-section {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-3);
  /* Lets the narrow-width layout below key off this section's own width (the admin sidebar eats
     a variable share of the screen), not the screen's. */
  container-type: inline-size;
}

/* Wide: a compact 3-column table with fixed column widths, so both tables line up with each other.
   Long names/emails wrap instead of widening it. */
.ds-table.fu-table {
  table-layout: fixed;
}
.fu-col-who {
  width: 34%;
}
.fu-col-actions {
  width: 344px; /* 3 x 104px buttons + gaps + cell padding */
}
.fu-who {
  min-width: 0;
}
.fu-who :deep(.ds-avatar-label-name),
.fu-who :deep(.ds-avatar-label-email) {
  overflow-wrap: anywhere;
}
.fu-info .fu-main {
  color: var(--ds-text-heading);
  font-weight: 500;
}
.fu-actions-cell {
  white-space: nowrap;
}
/* Three 32px icon columns (Remind / View / Remove) so every row's buttons line up. */
.fu-actions {
  display: grid;
  grid-template-columns: repeat(3, 32px);
  gap: var(--ds-space-2);
  justify-content: end;
  align-items: center;
}
.fu-actions > * {
  width: 100%;
  justify-content: center;
  white-space: nowrap;
}

/* Narrow: each row becomes a card — no table, no sideways scroll. */
@container (max-width: 720px) {
  .ds-table.fu-table {
    min-width: 0; /* the shared table style forces 480px */
  }
  .fu-table thead {
    display: none;
  }
  .fu-table,
  .fu-table tbody,
  .fu-table tr,
  .fu-table td {
    display: block;
    width: 100%;
    box-sizing: border-box;
  }
  .fu-table tr {
    padding: var(--ds-space-4);
    border-bottom: 1px solid var(--ds-border-hairline);
  }
  .fu-table tr:last-child {
    border-bottom: none;
  }
  .fu-table td {
    padding: 0 0 var(--ds-space-3);
    border: 0;
  }
  .fu-table td:last-child {
    padding-bottom: 0;
  }
  .fu-actions {
    display: flex;
    gap: var(--ds-space-2);
  }
  .fu-actions > * {
    flex: 0 0 32px;
  }
  .fu-slot {
    display: none;
  }
}
</style>
