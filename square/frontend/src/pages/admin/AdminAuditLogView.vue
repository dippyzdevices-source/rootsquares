<script setup lang="ts">
import BaseMultiSelect from '../../components/ui/BaseMultiSelect.vue'
import { ref, onMounted, watch, computed } from 'vue'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import { fetchAuditLog, exportAuditLog, type AuditLogEntry } from '../../services/adminAuditApi'
import { downloadBlob } from '../../utils/download'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const toast = useToast()

const entries = ref<AuditLogEntry[]>([])
const loading = ref(true)
const loadError = ref(false)
const search = ref('')
const action = ref<string[]>([])
const page = ref(1)
const total = ref(0)
const totalPages = ref(1)

const { options: auditActions, label: actionLabel } = useLookup('audit_action')
const actionOptions = computed(() => auditActions.value)

function formatDatePart(value: string): string {
  return new Date(value).toLocaleDateString()
}

function formatTimePart(value: string): string {
  return new Date(value).toLocaleTimeString()
}

const exporting = ref(false)

async function handleExport() {
  exporting.value = true
  try {
    const blob = await exportAuditLog({ action: action.value, q: search.value || undefined })
    downloadBlob(blob, 'audit-log.xlsx')
  } catch {
    toast.error('Could not export the audit log')
  } finally {
    exporting.value = false
  }
}

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const response = await fetchAuditLog({
      action: action.value,
      q: search.value || undefined,
      page: page.value,
    })
    entries.value = response.items
    total.value = response.total
    totalPages.value = response.total_pages
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function goToPage(next: number) {
  page.value = next
  load()
}

function onSearch() {
  page.value = 1
  load()
}

watch(action, () => {
  page.value = 1
  load()
})
onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">Audit Log</h1>
        </div>
        <BaseButton size="sm" type="button" variant="secondary" class="export-audit-log" :disabled="exporting" @click="handleExport">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
          {{ exporting ? 'Exporting…' : 'Export to Excel' }}
        </BaseButton>
      </div>

      <hr class="ds-section-line" />

      <div class="ds-toolbar">
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Description" @keyup.enter="onSearch" />
        <BaseMultiSelect size="sm" class="ds-toolbar-select-wide" v-model="action" :options="actionOptions" all-label="All actions" aria-label="Filter by action" highlight-active />
      </div>

      <BaseLoadingState v-if="loading" label="Loading audit log…" />
      <div v-else-if="loadError" class="ds-alert ds-alert-danger"><div>Could not load the audit log.</div></div>
      <div v-else-if="entries.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
        <p class="ds-meta">No audit log entries yet.</p>
      </div>
      <template v-else>
        <div class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="entry in entries" :key="entry.id">
                  <td style="white-space: nowrap">
                    {{ formatDatePart(entry.created_at) }}
                    <div class="ds-caption">{{ formatTimePart(entry.created_at) }}</div>
                  </td>
                  <td>
                    <span style="display: inline-flex; align-items: center; gap: var(--ds-space-3)">
                      <BaseAvatar :name="entry.actor_name ?? entry.actor_email" size="sm" />
                      <span>
                        {{ entry.actor_name ?? entry.actor_email ?? '—' }}
                        <div v-if="entry.actor_name" class="ds-caption">{{ entry.actor_email }}</div>
                      </span>
                    </span>
                  </td>
                  <td><span class="ds-badge ds-badge-neutral">{{ actionLabel(entry.action) }}</span></td>
                  <td>{{ entry.description }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <PaginationBar :page="page" :total-pages="totalPages" :total="total" @update:page="goToPage" />
      </template>
    </div>
  </div>
</template>
