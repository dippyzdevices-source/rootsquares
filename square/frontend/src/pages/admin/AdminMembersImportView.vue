<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import BaseAlert from '../../components/ui/BaseAlert.vue'
import MemberSectionNav from '../../components/MemberSectionNav.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseFileButton from '../../components/ui/BaseFileButton.vue'
import BaseCard from '../../components/ui/BaseCard.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseTable from '../../components/ui/BaseTable.vue'
import {
  previewMembersImport,
  confirmMembersImport,
  fetchImportHistory,
  type ImportRowPreview,
  type ImportBatch,
} from '../../services/adminImportsApi'
import { formatEventDate } from '../../utils/date'
import { useToast } from '../../composables/useToast'

const toast = useToast()

const filename = ref('')
const previewing = ref(false)
const confirming = ref(false)
const rows = ref<ImportRowPreview[]>([])
const validCount = ref(0)
const invalidCount = ref(0)
const result = ref<ImportBatch | null>(null)
const history = ref<ImportBatch[]>([])
const loadingHistory = ref(true)

const validRows = computed(() => rows.value.filter((row) => Object.keys(row.errors).length === 0))

const columns = [
  { key: 'row_number', label: '#' },
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
  { key: 'parent_email', label: 'Parent' },
  { key: 'membership_type', label: 'Type' },
  { key: 'errors', label: 'Errors' },
]

function asRow(row: Record<string, unknown>): ImportRowPreview {
  return row as unknown as ImportRowPreview
}

function rowErrors(row: ImportRowPreview): string {
  return Object.values(row.errors).join(' ')
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  filename.value = file.name
  result.value = null
  previewing.value = true
  try {
    const response = await previewMembersImport(file)
    rows.value = response.rows
    validCount.value = response.valid_count
    invalidCount.value = response.invalid_count
  } catch {
    toast.error('Could not read this file')
  } finally {
    previewing.value = false
  }
}

async function confirmImport() {
  confirming.value = true
  try {
    // row_number stays in the payload so a row skipped at confirm can be named in the failure list.
    const payload = validRows.value.map(({ errors, ...fields }) => fields)
    result.value = await confirmMembersImport(filename.value, payload)
    toast.success('Import confirmed')
    rows.value = []
    await loadHistory()
  } catch {
    toast.error('Could not confirm this import')
  } finally {
    confirming.value = false
  }
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    history.value = (await fetchImportHistory()).items
  } catch {
    // History is secondary — not worth blocking the import UI over.
  } finally {
    loadingHistory.value = false
  }
}

onMounted(loadHistory)
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div class="ds-heading">
      <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
      <h1 class="ds-display ds-display-s">Members</h1>
    </div>

    <MemberSectionNav />

    <div class="max-w-3xl space-y-8">

    <BaseCard class="space-y-4">
      <p class="text-sm text-text-secondary">
        Upload an .xlsx file with columns: name, email, phone, address, family_info,
        membership_type, membership_status, start_date, end_date, parent_email. For a child, fill
        parent_email (the parent's email), set membership_type to child, and leave email blank if
        they have none — the parent must already be an active member, or an active adult in this
        same file. Nothing is saved until you confirm.
      </p>
      <div style="display: flex; align-items: center; gap: var(--ds-space-3); flex-wrap: wrap">
        <BaseFileButton accept=".xlsx" size="sm" :disabled="previewing" @change="handleFileSelect">Choose .xlsx file</BaseFileButton>
        <span v-if="filename" class="ds-meta">{{ filename }}</span>
      </div>
      <p v-if="previewing" class="text-sm text-text-secondary">Reading file…</p>
    </BaseCard>

    <template v-if="rows.length > 0">
      <BaseAlert :variant="invalidCount > 0 ? 'error' : 'success'">
        {{ validCount }} valid, {{ invalidCount }} invalid out of {{ rows.length }} rows.
      </BaseAlert>

      <BaseTable :columns="columns" :rows="rows">
        <template #cell-errors="{ row }">
          <span class="text-sm text-error">{{ rowErrors(asRow(row)) }}</span>
        </template>
      </BaseTable>

      <BaseButton size="sm"
        variant="primary"
        class="confirm-import"
        :disabled="confirming || validCount === 0"
        @click="confirmImport"
      >
        {{ confirming ? 'Confirming…' : `Confirm import (${validCount} rows)` }}
      </BaseButton>
    </template>

    <BaseCard v-if="result" class="space-y-1">
      <p class="text-sm text-text">
        {{ result.members_created }} member(s) created, {{ result.memberships_created }}
        membership(s) created, {{ result.failed_rows }} row(s) failed.
      </p>
      <ul v-if="result.failures?.length" class="import-failures text-sm text-error">
        <li v-for="(failure, index) in result.failures" :key="index">
          Row {{ failure.row_number ?? '?' }}<template v-if="failure.name"> ({{ failure.name }})</template>:
          {{ failure.reason }}
        </li>
      </ul>
    </BaseCard>

    <section class="space-y-3">
      <h2 class="text-lg font-semibold text-text">Recent imports</h2>
      <BaseLoadingState v-if="loadingHistory" label="Loading import history…" />
      <p v-else-if="history.length === 0" class="text-sm text-text-secondary">No imports yet.</p>
      <BaseCard v-for="batch in history" v-else :key="batch.id" class="space-y-1">
        <div class="flex items-center justify-between">
          <p class="text-sm font-medium text-text">{{ batch.filename }}</p>
          <p class="text-xs text-text-secondary">{{ formatEventDate(batch.created_at) }}</p>
        </div>
        <p class="text-sm text-text-secondary">
          {{ batch.members_created }} members, {{ batch.memberships_created }} memberships,
          {{ batch.failed_rows }} failed — by {{ batch.admin_email }}
        </p>
      </BaseCard>
    </section>
    </div>
  </div>
</template>
