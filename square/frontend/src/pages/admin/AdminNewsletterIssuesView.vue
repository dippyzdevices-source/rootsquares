<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import FilterPills from '../../components/ui/FilterPills.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import NewsletterSectionNav from '../../components/NewsletterSectionNav.vue'
import { fetchMessages, type AdminMessage } from '../../services/messagesApi'
import { moduleEnabled } from '../../services/modules'
import { useToast } from '../../composables/useToast'
import { formatDateTime } from '../../utils/date'

// Newsletters are Messages sent to the subscribers (W14-R19): this tab lists those, the editor is the Messages composer with the audience preset.
const toast = useToast()
const router = useRouter() as ReturnType<typeof useRouter> | undefined
const messagesOn = moduleEnabled('messages')

const items = ref<AdminMessage[]>([])
const total = ref(0)
const page = ref(1)
const perPage = 25
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / perPage)))
const loading = ref(true)
const search = ref('')
const filter = ref('all')
const filterOptions = [{ value: 'all', label: 'All' }, ...['draft', 'scheduled', 'sending', 'sent'].map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))]
const visible = computed(() => {
  const q = search.value.trim().toLowerCase()
  return items.value.filter((m) => (filter.value === 'all' || m.status === filter.value) && (!q || m.subject.toLowerCase().includes(q)))
})

const STATUS_LABEL: Record<string, string> = { draft: 'Draft', scheduled: 'Scheduled', sending: 'Sending', sent: 'Sent' }
const tone = (s: string) => (s === 'sent' ? 'ds-badge-success' : s === 'scheduled' ? 'ds-badge-info' : s === 'sending' ? 'ds-badge-warning' : 'ds-badge-neutral')

async function load() {
  if (!messagesOn) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const result = await fetchMessages(page.value, 'subscribers')
    items.value = result.items
    total.value = result.total
  } catch {
    toast.error('Could not load newsletters')
  } finally {
    loading.value = false
  }
}
watch(page, load)
onMounted(load)

function open(event: MouseEvent, message: AdminMessage) {
  if ((event.target as HTMLElement).closest('a, button')) return
  void router?.push(`/admin/messages/${message.id}`)
}
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Newsletter</h1>
      </div>
      <BaseButton v-if="messagesOn" to="/admin/messages/new?audience=subscribers" variant="secondary" size="sm" class="new-newsletter">New newsletter</BaseButton>
    </div>

    <NewsletterSectionNav />

    <div v-if="messagesOn" class="ds-toolbar">
      <FilterPills v-model="filter" :options="filterOptions" label="Filter newsletters by status" />
      <BaseSearchField v-model="search" size="sm" class="ds-toolbar-search" placeholder="Search by subject…" aria-label="Search newsletters" />
    </div>

    <div v-if="!messagesOn" class="ds-alert ds-alert-warning">
      <div>Newsletters are written and sent in Messages. Switch on the Messages module for this square to write one.</div>
    </div>
    <BaseLoadingState v-else-if="loading" label="Loading newsletters…" />
    <div v-else-if="items.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
      <p class="ds-meta">No newsletters yet. Write your first one.</p>
    </div>
    <div v-else-if="visible.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
      <p class="ds-meta">Nothing matches this filter or search.</p>
    </div>
    <div v-else class="ds-table-wrap">
      <div class="ds-table-scroll">
        <table class="ds-table">
          <thead>
            <tr>
              <th>Subject</th>
              <th>Status</th>
              <th>When</th>
              <th data-align="right">Delivered</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in visible" :key="m.id" class="ds-row-clickable" @click="open($event, m)">
              <td data-emphasis>{{ m.subject }}</td>
              <td><span class="ds-badge" :class="tone(m.status)">{{ STATUS_LABEL[m.status] ?? m.status }}</span></td>
              <td>{{ m.status === 'scheduled' && m.scheduled_for ? formatDateTime(m.scheduled_for) : m.sent_at ? formatDateTime(m.sent_at) : formatDateTime(m.created_at) }}</td>
              <td data-align="right">
                <template v-if="m.status === 'draft' || m.status === 'scheduled'">—</template>
                <template v-else>{{ m.sent_count }} / {{ m.recipients_total - m.skipped_count }}<span v-if="m.failed_count"> · {{ m.failed_count }} failed</span></template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <PaginationBar v-if="messagesOn && items.length" v-model:page="page" :total-pages="totalPages" :total="total" />
  </div>
</template>
