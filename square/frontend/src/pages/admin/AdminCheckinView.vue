<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchCheckinSummary, type CheckinSummary } from '../../services/checkinApi'
import { fetchAdminTickets, type AdminTicketRecord } from '../../services/adminTicketsApi'

const loading = ref(true)
const summary = ref<CheckinSummary | null>(null)
const recentScans = ref<AdminTicketRecord[]>([])

const remaining = computed(() =>
  summary.value ? summary.value.total_tickets - summary.value.checked_in_count : null,
)
const ratePct = computed(() => {
  if (!summary.value || summary.value.total_tickets === 0) return 0
  return Math.round((summary.value.checked_in_count / summary.value.total_tickets) * 100)
})

function formatScanDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString()
}

function formatScanTime(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString()
}

onMounted(async () => {
  loading.value = true
  try {
    const [summaryData, ticketsData] = await Promise.all([
      fetchCheckinSummary(),
      fetchAdminTickets({ status: 'used', perPage: 10, sort: 'checked_in_at_desc' }),
    ])
    summary.value = summaryData
    recentScans.value = ticketsData.items
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
        <h1 class="ds-display ds-display-s">Check-in</h1>
      </div>

      <hr class="ds-section-line" />

      <div class="ds-alert ds-alert-info checkin-banner">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0"><rect x="5" y="2" width="14" height="20" rx="2" /><line x1="12" y1="18" x2="12.01" y2="18" /></svg>
        <div class="checkin-banner-text">
          <strong class="ds-alert-title">Check-in runs on a phone at the door</strong>
          <p style="margin: 0">
            Sign in on the duty phone and keep it on the venue wifi. A volunteer can jump
            straight to the scanner from their account menu — no admin access needed.
          </p>
        </div>
        <BaseButton to="/checkin" variant="primary" size="sm" class="checkin-banner-action">
          Open the scanner
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
        </BaseButton>
      </div>

      <BaseLoadingState v-if="loading" label="Loading check-in overview…" />
      <template v-else>
        <div class="ds-cards" style="grid-template-columns: repeat(auto-fit, minmax(180px, 1fr))">
          <div class="ds-card">
            <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow); color: var(--ds-text-primary)">Checked in</p>
            <div style="font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); color: var(--ds-text-primary); margin-top: 4px">{{ summary?.checked_in_count ?? '—' }}</div>
          </div>
          <div class="ds-card">
            <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Not yet checked in</p>
            <div style="font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); color: var(--ds-text-heading); margin-top: 4px">{{ remaining ?? '—' }}</div>
          </div>
          <div class="ds-card">
            <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Check-in rate</p>
            <div style="font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); color: var(--ds-text-heading); margin-top: 4px">{{ ratePct }}%</div>
          </div>
        </div>

        <section style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <h2 class="ds-title">Last scans</h2>
          <div v-if="recentScans.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
            <p class="ds-meta">No check-ins yet.</p>
          </div>
          <div v-else class="ds-table-wrap">
            <div class="ds-table-scroll">
              <table class="ds-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Customer</th>
                    <th>Ticket</th>
                    <th>Checked in by</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="ticket in recentScans" :key="ticket.id">
                    <td style="white-space: nowrap">
                      {{ formatScanDate(ticket.checked_in_at) }}
                      <div v-if="ticket.checked_in_at" class="ds-caption">{{ formatScanTime(ticket.checked_in_at) }}</div>
                    </td>
                    <td>
                      <span style="display: inline-flex; align-items: center; gap: var(--ds-space-3)">
                        <BaseAvatar :name="ticket.customer_name" size="sm" />
                        <span>
                          {{ ticket.customer_name }}
                          <div class="ds-caption">{{ ticket.customer_email }}</div>
                        </span>
                      </span>
                    </td>
                    <td data-emphasis>
                      <span style="white-space: nowrap; font-variant-numeric: tabular-nums">{{ ticket.ticket_code }}</span>
                      <div class="ds-caption">{{ ticket.ticket_type }} · {{ ticket.event_title }}</div>
                    </td>
                    <td>
                      <span style="display: inline-flex; align-items: center; gap: var(--ds-space-3)">
                        <BaseAvatar :name="ticket.checked_in_by_name ?? ticket.checked_in_by" size="sm" />
                        <span>
                          {{ ticket.checked_in_by_name ?? ticket.checked_in_by ?? '—' }}
                          <div v-if="ticket.checked_in_by_name" class="ds-caption">{{ ticket.checked_in_by }}</div>
                        </span>
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* The banner wraps instead of squeezing: on a phone the text gets the full row width and the
   button drops below it, full width. */
.checkin-banner { flex-wrap: wrap; }
.checkin-banner-text { flex: 1 1 260px; min-width: 0; }
.checkin-banner-action { flex-shrink: 0; }
@media (max-width: 640px) {
  .checkin-banner-action { flex: 1 1 100%; }
}
</style>
