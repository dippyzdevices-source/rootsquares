<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import BaseMultiSelect from '../../components/ui/BaseMultiSelect.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { PAGE_SIZE } from '../../composables/useClientPagination'
import NewsletterSectionNav from '../../components/NewsletterSectionNav.vue'
import {
  fetchSubscribers,
  exportSubscribers,
  deleteSubscriber,
  type Subscriber,
} from '../../services/adminNewsletterApi'
import { downloadBlob } from '../../utils/download'
import { formatEventDate } from '../../utils/date'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: newsletterStatusLabel } = useLookup('newsletter_status')
const toast = useToast()

const items = ref<Subscriber[]>([])
const page = ref(1)
const totalPages = ref(1)
const subscribedCount = ref(0)
const total = ref(0)
const loading = ref(true)
const error = ref(false)
const query = ref('')
const status = ref<string[]>([])
const exporting = ref(false)

const statusOptions = computed(() => [
  { value: 'subscribed', label: newsletterStatusLabel('subscribed') },
  { value: 'pending', label: newsletterStatusLabel('pending') },
  { value: 'unsubscribed', label: newsletterStatusLabel('unsubscribed') },
])

async function load() {
  loading.value = true
  error.value = false
  try {
    const data = await fetchSubscribers({ q: query.value, status: status.value, perPage: PAGE_SIZE, page: page.value })
    totalPages.value = data.total_pages
    items.value = data.items
    total.value = data.total
    subscribedCount.value = data.subscribed_count
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function handleExport() {
  exporting.value = true
  try {
    downloadBlob(await exportSubscribers(status.value, query.value), 'newsletter-subscribers.xlsx')
  } catch {
    toast.error('Could not export subscribers')
  } finally {
    exporting.value = false
  }
}

async function remove(subscriber: Subscriber) {
  try {
    await deleteSubscriber(subscriber.id)
    toast.success('Subscriber erased')
    await load()
  } catch {
    toast.error('Could not erase this subscriber')
  }
}

// Filter/search changes go back to page 1 (the page watcher does the load when it moves).
function reload() {
  if (page.value !== 1) page.value = 1
  else load()
}

watch(status, reload)
watch(page, load)
onMounted(load)
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Newsletter</h1>
      </div>
      <BaseButton size="sm" type="button" variant="secondary" class="export-subscribers" :disabled="exporting" @click="handleExport">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
        {{ exporting ? 'Exporting…' : 'Export to Excel' }}
      </BaseButton>
    </div>

    <NewsletterSectionNav />

    <p class="ds-meta">{{ subscribedCount }} active subscriber{{ subscribedCount === 1 ? '' : 's' }}</p>

    <div class="ds-toolbar">
      <BaseSearchField size="sm" class="ds-toolbar-search" v-model="query" placeholder="Search by email" @keyup.enter="reload" />
      <BaseMultiSelect size="sm" class="ds-toolbar-select-wide" v-model="status" :options="statusOptions" all-label="All" aria-label="Filter by status" highlight-active />
    </div>

    <BaseLoadingState v-if="loading" label="Loading subscribers…" />
    <div v-else-if="error" class="ds-alert ds-alert-danger"><div>Could not load subscribers.</div></div>
    <div v-else-if="items.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
      <p class="ds-meta">No subscribers yet.</p>
    </div>
    <div v-else class="ds-table-wrap">
      <div class="ds-table-scroll">
        <table class="ds-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Status</th>
              <th>Consent given</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="subscriber in items" :key="subscriber.id">
              <td data-emphasis>{{ subscriber.email }}</td>
              <td>
                <span class="ds-badge" :class="subscriber.status === 'subscribed' ? 'ds-badge-success' : subscriber.status === 'pending' ? 'ds-badge-warning' : 'ds-badge-neutral'">
                  {{ newsletterStatusLabel(subscriber.status) }}
                </span>
              </td>
              <td>{{ subscriber.consented_at ? formatEventDate(subscriber.consented_at) : '—' }}</td>
              <td data-align="right">
                <BaseIconButton variant="danger" size="sm" class="erase-subscriber" :label="`Erase ${subscriber.email}`" @click="remove(subscriber)">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" /></svg>
                </BaseIconButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />
    </div>
  </div>
</template>
