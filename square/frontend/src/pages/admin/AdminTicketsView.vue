<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import BaseMultiSelect from '../../components/ui/BaseMultiSelect.vue'
import { useEventFilterOptions } from '../../composables/useEventFilterOptions'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import {
  fetchAdminTickets,
  exportTickets,
  type AdminTicketRecord,
} from '../../services/adminTicketsApi'
import { downloadBlob } from '../../utils/download'
import { formatDateTime } from '../../utils/date'
import { ticketStatusVariant } from '../../utils/ticketStatus'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: ticketStatusLabel } = useLookup('ticket_status')
const toast = useToast()
const router = useRouter() as ReturnType<typeof useRouter> | undefined

// A ticket has no page of its own — tapping a row opens the order it belongs to.
function openTicketOrder(event: MouseEvent, ticket: AdminTicketRecord) {
  if ((event.target as HTMLElement).closest('a, button')) return
  void router?.push(`/admin/orders/${ticket.order_id}`)
}

const tickets = ref<AdminTicketRecord[]>([])
const page = ref(1)
const totalPages = ref(1)
const total = ref(0)
const loading = ref(true)
const loadError = ref(false)
const search = ref('')
const status = ref<string[]>([])
const eventId = ref<string[]>([])
const { eventOptions } = useEventFilterOptions()
const exporting = ref(false)

const statusOptions = computed(() => [
  { value: 'valid', label: ticketStatusLabel('valid') },
  { value: 'used', label: ticketStatusLabel('used') },
  { value: 'void', label: ticketStatusLabel('void') },
])

function statusTone(value: string): string {
  const variant = ticketStatusVariant(value)
  if (variant === 'success') return 'ds-badge-success'
  if (variant === 'error') return 'ds-badge-danger'
  return 'ds-badge-neutral'
}

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const response = await fetchAdminTickets({
      page: page.value,
      status: status.value,
      q: search.value || undefined,
      eventId: eventId.value,
    })
    tickets.value = response.items
    totalPages.value = response.total_pages
    total.value = response.total
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

async function handleExport() {
  exporting.value = true
  try {
    const blob = await exportTickets({
      status: status.value,
      q: search.value || undefined,
      eventId: eventId.value,
    })
    downloadBlob(blob, 'tickets.xlsx')
  } catch {
    toast.error('Could not export tickets')
  } finally {
    exporting.value = false
  }
}

// Filter/search changes go back to page 1 (the page watcher does the load when it moves).
function reload() {
  if (page.value !== 1) page.value = 1
  else load()
}

watch([status, eventId], reload)
watch(page, load)
onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">Tickets</h1>
        </div>
          <BaseButton size="sm" to="/admin/tickets/message" variant="secondary" class="message-buyers">Message buyers</BaseButton>
          <BaseButton size="sm" type="button" variant="secondary" class="export-tickets" :disabled="exporting" @click="handleExport">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
          {{ exporting ? 'Exporting…' : 'Export to Excel' }}
        </BaseButton>
      </div>

      <hr class="ds-section-line" />

      <div class="ds-toolbar">
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Code, name, or email" @keyup.enter="reload" />
        <BaseMultiSelect size="sm" class="ds-toolbar-select-wide" v-model="eventId" :options="eventOptions" all-label="All events" aria-label="Filter by event" highlight-active />
        <BaseMultiSelect size="sm" class="ds-toolbar-select-wide" v-model="status" :options="statusOptions" all-label="All statuses" aria-label="Filter by status" highlight-active />
      </div>

      <BaseLoadingState v-if="loading" label="Loading tickets…" />
      <div v-else-if="loadError" class="ds-alert ds-alert-danger"><div>Could not load tickets.</div></div>
      <div v-else-if="tickets.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
        <p class="ds-meta">No tickets yet.</p>
      </div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Customer</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ticket in tickets" :key="ticket.id" class="ds-row-clickable" @click="openTicketOrder($event, ticket)">
                <td data-emphasis>
                  <span style="white-space: nowrap; font-variant-numeric: tabular-nums">{{ ticket.ticket_code }}</span>
                  <div class="ds-caption">{{ ticket.event_title }}</div>
                </td>
                <td>
                  {{ ticket.customer_name }}
                  <div class="ds-caption">{{ ticket.customer_email }}</div>
                </td>
                <td style="white-space: nowrap">
                  <span class="ds-badge" :class="statusTone(ticket.status)">{{ ticketStatusLabel(ticket.status) }}</span>
                  <div v-if="ticket.status === 'used' && ticket.checked_in_at" class="ds-caption">
                    {{ formatDateTime(ticket.checked_in_at) }}<template v-if="ticket.checked_in_by_name ?? ticket.checked_in_by"> · {{ ticket.checked_in_by_name ?? ticket.checked_in_by }}</template>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />
    </div>
  </div>
</template>
