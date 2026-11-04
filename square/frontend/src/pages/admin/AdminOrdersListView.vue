<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import BaseMultiSelect from '../../components/ui/BaseMultiSelect.vue'
import { useEventFilterOptions } from '../../composables/useEventFilterOptions'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { fetchAdminOrders, exportOrders, type AdminOrder } from '../../services/adminOrdersApi'
import { formatPrice } from '../../utils/money'
import { downloadBlob } from '../../utils/download'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: paymentStatusLabel } = useLookup('payment_status')
const toast = useToast()
// Optional so the page still mounts in isolation (tests).
const router = useRouter() as ReturnType<typeof useRouter> | undefined

// Tapping anywhere on a row opens the order; real links/buttons inside it keep their own action.
function openOrder(event: MouseEvent, order: AdminOrder) {
  if ((event.target as HTMLElement).closest('a, button')) return
  void router?.push(`/admin/orders/${order.id}`)
}
const route = useRoute()

const orders = ref<AdminOrder[]>([])
const page = ref(1)
const totalPages = ref(1)
const total = ref(0)
const loading = ref(true)
const exporting = ref(false)

const statusOptions = computed(() => [
  { value: 'pending', label: paymentStatusLabel('pending') },
  { value: 'pending_verification', label: paymentStatusLabel('pending_verification') },
  { value: 'paid', label: paymentStatusLabel('paid') },
  { value: 'rejected', label: paymentStatusLabel('rejected') },
  { value: 'failed', label: paymentStatusLabel('failed') },
  { value: 'cancelled', label: paymentStatusLabel('cancelled') },
  { value: 'refunded', label: paymentStatusLabel('refunded') },
])
// Pre-selects the filter from a `?status=` query param (e.g. the dashboard's "Pending
// orders" card, which sends `pending,pending_verification`) so arriving here already shows the relevant subset.
const initialStatuses = (typeof route.query.status === 'string' ? route.query.status : '').split(',')
const search = ref('')
const eventId = ref<string[]>([])
const { eventOptions } = useEventFilterOptions()
const paymentStatus = ref<string[]>(initialStatuses.filter((s) => statusOptions.value.some((opt) => opt.value === s)))

function statusTone(value: string): string {
  if (value === 'paid') return 'ds-badge-success'
  if (value === 'failed' || value === 'cancelled' || value === 'rejected') return 'ds-badge-danger'
  if (value === 'refunded') return 'ds-badge-info'
  if (value === 'pending_verification') return 'ds-badge-accent'
  return 'ds-badge-neutral'
}

async function load() {
  loading.value = true
  const response = await fetchAdminOrders({
    page: page.value,
    paymentStatus: paymentStatus.value,
    q: search.value || undefined,
    eventId: eventId.value,
  })
  orders.value = response.items
  totalPages.value = response.total_pages
  total.value = response.total
  loading.value = false
}

async function handleExport() {
  exporting.value = true
  try {
    const blob = await exportOrders({
      paymentStatus: paymentStatus.value,
      q: search.value || undefined,
      eventId: eventId.value,
    })
    downloadBlob(blob, 'orders.xlsx')
  } catch {
    toast.error('Could not export orders')
  } finally {
    exporting.value = false
  }
}

// Search/filter changes go back to page 1 (the page watcher does the load when it moves).
function reload() {
  if (page.value !== 1) page.value = 1
  else load()
}

watch([paymentStatus, eventId], reload)
watch(page, load)
onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">Orders</h1>
        </div>
          <BaseButton size="sm" type="button" variant="secondary" class="export-orders" :disabled="exporting" @click="handleExport">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
          {{ exporting ? 'Exporting…' : 'Export to Excel' }}
        </BaseButton>
      </div>

      <hr class="ds-section-line" />

      <div class="ds-toolbar">
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Order number, name, email, or phone" @keyup.enter="reload" />
        <BaseMultiSelect size="sm" class="ds-toolbar-select-wide" v-model="eventId" :options="eventOptions" all-label="All events" aria-label="Filter by event" highlight-active />
        <BaseMultiSelect size="sm" class="ds-toolbar-select-wide" v-model="paymentStatus" :options="statusOptions" all-label="All statuses" aria-label="Filter by status" highlight-active />
      </div>

      <BaseLoadingState v-if="loading" label="Loading orders…" />
      <div v-else-if="orders.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
        <p class="ds-meta">No orders yet.</p>
      </div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table" style="min-width: 760px; table-layout: fixed">
            <colgroup>
              <col style="width: 210px" />
              <col />
              <col style="width: 120px" />
              <col style="width: 140px" />
              <col style="width: 60px" />
            </colgroup>
            <thead>
              <tr>
                <th>Order</th>
                <th>Customer</th>
                <th data-align="right">Total</th>
                <th>Payment</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="order in orders" :key="order.id" class="ds-row-clickable" @click="openOrder($event, order)">
                <td data-emphasis>
                  {{ order.order_number }}
                  <div v-if="order.event_title" class="ds-caption">{{ order.event_title }}</div>
                </td>
                <td style="overflow: hidden">
                  <span style="display: inline-flex; align-items: center; gap: var(--ds-space-2); min-width: 0; max-width: 100%">
                    <BaseAvatar :name="order.customer_name" size="sm" />
                    <span style="min-width: 0; overflow: hidden">
                      <div style="font-weight: 600; color: var(--ds-text-heading); overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="order.customer_name ?? undefined">{{ order.customer_name ?? order.customer_email ?? '—' }}</div>
                      <div v-if="order.customer_name && order.customer_email" class="ds-caption" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="order.customer_email">{{ order.customer_email }}</div>
                    </span>
                  </span>
                </td>
                <td data-align="right">{{ formatPrice(order.total_amount) }}</td>
                <td><span class="ds-badge" :class="statusTone(order.payment_status)">{{ paymentStatusLabel(order.payment_status) }}</span></td>
                <td data-align="right">
                  <BaseIconButton variant="bare" :to="`/admin/orders/${order.id}`" size="sm" :label="`View order ${order.order_number}`">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" /><circle cx="12" cy="12" r="3" /></svg>
                  </BaseIconButton>
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
