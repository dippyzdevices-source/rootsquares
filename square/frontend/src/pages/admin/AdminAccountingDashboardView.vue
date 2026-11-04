<script setup lang="ts">
import { moduleEnabled } from '../../services/modules'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import BaseMultiSelect from '../../components/ui/BaseMultiSelect.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { useClientPagination } from '../../composables/useClientPagination'
import AccountingExpenseModal from './AccountingExpenseModal.vue'
import AccountingContributionModal from './AccountingContributionModal.vue'
import AccountingExpenseViewModal from './AccountingExpenseViewModal.vue'
import AccountingReceiptModal from './AccountingReceiptModal.vue'
import {
  fetchEventAccountingSummary,
  fetchEventCollections,
  downloadEventReport,
  exportEventBuyers,
  exportEventExpenses,
  fetchEventExpenses,
  deleteExpense,
  fetchEventContributions,
  updateContribution,
  deleteContribution,
  type Contribution,
  type AccountingEventSummary,
  type CollectionItem,
  type Expense,
} from '../../services/adminAccountingApi'
import { fetchAdminTicketTypes } from '../../services/adminTicketTypesApi'
import { formatPriceGrouped as formatPrice, formatPriceRoundedGrouped as formatPriceRounded } from '../../utils/money'
import { downloadBlob } from '../../utils/download'
import { formatEventDate } from '../../utils/date'
import { formatTicketDayShort } from '../../utils/ticketDays'
import { eventPhase, EVENT_PHASE_BADGE, EVENT_PHASE_LABEL } from '../../utils/eventPhase'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: providerLabel } = useLookup('payment_provider')
const { label: paymentStatusLabel } = useLookup('payment_status')
const route = useRoute()
const toast = useToast()

// Draft / Live / Expired marker beside the title (same wording and look as the Accounting events list).
const ticketsOn = moduleEnabled('tickets') // W8-R29: ticket figures and collections belong to the Tickets module
const checkinOn = moduleEnabled('checkin') // W8-R22: the check-in rate belongs to the Check-in module
const checkinRate = computed(() => {
  const s = summary.value
  if (!s || s.tickets_expected === 0) return 0
  return Math.round((s.tickets_checked_in / s.tickets_expected) * 100)
})

const phase = computed(() => (summary.value ? eventPhase(summary.value.event) : null))

// Single-day or multi-day, with the dates (browser-local days, like the rest of the page).
const schedule = computed(() => {
  const ev = summary.value?.event
  if (!ev) return { kind: '', dates: '' }
  const start = new Date(ev.start_datetime)
  const end = ev.end_datetime ? new Date(ev.end_datetime) : null
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const time = (d: Date) => d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  if (!end || day(start) === day(end)) {
    return { kind: 'Single-day event', dates: `${formatEventDate(ev.start_datetime)} · ${time(start)}${end ? ` – ${time(end)}` : ''}` }
  }
  const days = Math.round((day(end) - day(start)) / 86400000) + 1
  return { kind: `Multi-day event · ${days} days`, dates: `${formatEventDate(ev.start_datetime)} – ${formatEventDate(ev.end_datetime as string)}` }
})

const eventId = computed(() => Number(route.params.eventId))

const summary = ref<AccountingEventSummary | null>(null)
const summaryLoading = ref(true)
const summaryError = ref(false)

const collections = ref<CollectionItem[]>([])
const { page: collPage, totalPages: collTotalPages, pageItems: collItems, total: collTotal } = useClientPagination(collections)
const collectionsLoading = ref(true)
const collectionsError = ref(false)
// Collections filters: the table and the Excel export both use them (search applies on Enter).
const collSearch = ref('')
const collMethod = ref<string[]>([])
const collTicketType = ref<string[]>([])
const collCoupon = ref<string[]>([])
// "Show details": a line under each order with what it bought (hidden by default); the PDF report follows it.
const showCollDetails = ref(false)
const collTicketTypeOptions = ref<{ value: string; label: string }[]>([])
const collFiltersActive = computed(() => !!(collSearch.value || collMethod.value.length || collCoupon.value.length || collTicketType.value.length))
const collFilter = () => ({
  q: collSearch.value || undefined,
  paymentMethods: collMethod.value,
  couponCodes: collCoupon.value,
  ticketTypeIds: collTicketType.value.map(Number),
})
// The coupons that were actually used on this event's paid orders (what the Collections can match).
const collCouponOptions = computed(() =>
  (summary.value?.coupon_usage ?? []).map((c) => ({ value: c.coupon_code, label: c.coupon_code })),
)
const collMethodOptions = computed(() => [
  { value: 'cash', label: providerLabel('cash') },
  { value: 'vipps_qr', label: providerLabel('vipps_qr') },
  { value: 'vipps_app', label: providerLabel('vipps_app') },
  { value: 'stripe', label: providerLabel('stripe') },
  ...(moduleEnabled('coupons') ? [{ value: 'coupon', label: 'Coupon (free)' }] : []), // W8-R21: coupons are the Coupons module's
])

const expenses = ref<Expense[]>([])
const { page: expPage, totalPages: expTotalPages, pageItems: expItems, total: expTotal } = useClientPagination(expenses)
const expensesLoading = ref(true)
const expensesError = ref(false)
const categoryFilter = ref<string[]>([])

const editTarget = ref<Expense | null>(null)
const showExpenseModal = ref(false)
const deleteTarget = ref<Expense | null>(null)
const viewingReceiptUrl = ref<string | null>(null)
const showReceiptViewer = ref(false)
const viewTarget = ref<Expense | null>(null)
const showViewModal = ref(false)

function openReceipt(url: string) {
  viewingReceiptUrl.value = url
  showReceiptViewer.value = true
}

function statusTone(value: string): string {
  if (value === 'paid') return 'ds-badge-success'
  if (value === 'failed' || value === 'cancelled' || value === 'rejected') return 'ds-badge-danger'
  if (value === 'refunded') return 'ds-badge-info'
  return 'ds-badge-neutral'
}

const { options: expenseCategories, label: categoryLabel } = useLookup('expense_category')

// Donations & sponsorships received (money in): recorded like expenses, counted in the Collection.
const contributions = ref<Contribution[]>([])
const {
  page: conPage,
  totalPages: conTotalPages,
  pageItems: conItems,
  total: conTotal,
} = useClientPagination(contributions)
const contributionsLoading = ref(true)
const contributionsError = ref(false)
const kindFilter = ref<string[]>([])
const KIND_FILTER_OPTIONS = [
  { value: 'donation', label: 'Donations' },
  { value: 'sponsorship', label: 'Sponsorships' },
]
const CONTRIBUTION_STATUS: Record<string, string> = { paid: 'Received', pending: 'Pending', failed: 'Failed', refunded: 'Refunded' }
const contributionTarget = ref<Contribution | null>(null)
const showContributionModal = ref(false)
const deleteContributionTarget = ref<Contribution | null>(null)

async function loadContributions() {
  contributionsLoading.value = true
  contributionsError.value = false
  try {
    contributions.value = (await fetchEventContributions(eventId.value, { kinds: kindFilter.value })).items
  } catch {
    contributionsError.value = true
  } finally {
    contributionsLoading.value = false
  }
}

function openAddContribution() {
  contributionTarget.value = null
  showContributionModal.value = true
}

function openEditContribution(c: Contribution) {
  contributionTarget.value = c
  showContributionModal.value = true
}

// One tap for a pending donation or sponsorship that has now arrived; an enquiry with no amount yet
// needs the amount first, so it opens the edit form instead.
async function markReceived(c: Contribution) {
  if (c.amount == null) {
    openEditContribution(c)
    return
  }
  try {
    await updateContribution(c.id, { status: 'paid' })
    toast.success('Marked as received')
    await Promise.all([loadContributions(), loadSummary()])
  } catch {
    toast.error('Could not update this entry')
  }
}

async function onContributionSaved() {
  await Promise.all([loadContributions(), loadSummary()])
}

async function confirmDeleteContribution() {
  if (!deleteContributionTarget.value) return
  try {
    await deleteContribution(deleteContributionTarget.value.id)
    toast.success('Deleted')
    deleteContributionTarget.value = null
    await Promise.all([loadContributions(), loadSummary()])
  } catch {
    toast.error('Could not delete this entry')
  }
}

async function loadSummary() {
  summaryLoading.value = true
  summaryError.value = false
  try {
    summary.value = await fetchEventAccountingSummary(eventId.value)
  } catch {
    summaryError.value = true
  } finally {
    summaryLoading.value = false
  }
}

const exportingExpenses = ref(false)
const commissionFor = (provider: string) =>
  // Ticket commission only: processing fees of online donations are an expense but not this channel's.
  ((f) => (f ? f.processing - (f.processing_donations ?? 0) : 0))(
    (summary.value?.fees_by_provider ?? []).find((x) => x.provider === provider),
  )
// Providers' processing fees: read-only expense lines, shown on the unfiltered first page.
const feeLines = ref<{ provider: string; amount: number }[]>([])
const showFeeLines = computed(() => feeLines.value.length > 0 && categoryFilter.value.length === 0 && expPage.value === 1)

async function handleExportExpenses() {
  exportingExpenses.value = true
  try {
    const blob = await exportEventExpenses(eventId.value, { categories: categoryFilter.value })
    downloadBlob(blob, `${summary.value?.event.slug ?? `event-${eventId.value}`}-expenses.xlsx`)
  } catch {
    toast.error('Could not export the expenses')
  } finally {
    exportingExpenses.value = false
  }
}

const downloadingReport = ref(false)
async function handleDownloadReport() {
  downloadingReport.value = true
  try {
    const blob = await downloadEventReport(eventId.value, { details: showCollDetails.value })
    downloadBlob(blob, `${summary.value?.event.slug ?? `event-${eventId.value}`}-accounting-report.pdf`)
  } catch {
    toast.error('Could not build the PDF report')
  } finally {
    downloadingReport.value = false
  }
}

const exportingBuyers = ref(false)

async function handleExportBuyers() {
  exportingBuyers.value = true
  try {
    const blob = await exportEventBuyers(eventId.value, collFilter())
    downloadBlob(blob, `${summary.value?.event.slug ?? `event-${eventId.value}`}-buyers.xlsx`)
  } catch {
    toast.error('Could not export the buyers list')
  } finally {
    exportingBuyers.value = false
  }
}

async function loadCollections() {
  collectionsLoading.value = true
  collectionsError.value = false
  try {
    collections.value = (await fetchEventCollections(eventId.value, collFilter())).items
    collPage.value = 1
  } catch {
    collectionsError.value = true
  } finally {
    collectionsLoading.value = false
  }
}

async function loadExpenses() {
  expensesLoading.value = true
  expensesError.value = false
  try {
    const data = await fetchEventExpenses(eventId.value, {
      categories: categoryFilter.value,
      perPage: 50,
    })
    expenses.value = data.items
    feeLines.value = data.processing_fee_lines ?? []
  } catch {
    expensesError.value = true
  } finally {
    expensesLoading.value = false
  }
}

async function loadAll() {
  await Promise.all([loadSummary(), loadCollections(), loadExpenses(), loadContributions()])
}

async function loadTicketTypeOptions() {
  try {
    const { items } = await fetchAdminTicketTypes(eventId.value)
    collTicketTypeOptions.value = items.map((t) => ({ value: String(t.id), label: t.name }))
  } catch {
    // the filter just stays on "All ticket types"
  }
}

onMounted(() => {
  void loadAll()
  void loadTicketTypeOptions()
})
watch([collMethod, collCoupon, collTicketType], () => void loadCollections())
watch(kindFilter, () => {
  conPage.value = 1
  void loadContributions()
})
watch(categoryFilter, () => {
  expPage.value = 1
  void loadExpenses()
})

function openAddExpense() {
  editTarget.value = null
  showExpenseModal.value = true
}

function openEditExpense(expense: Expense) {
  editTarget.value = expense
  showExpenseModal.value = true
}

function openViewExpense(expense: Expense) {
  viewTarget.value = expense
  showViewModal.value = true
}

function editFromViewModal(expense: Expense) {
  showViewModal.value = false
  openEditExpense(expense)
}

async function onExpenseSaved() {
  await Promise.all([loadExpenses(), loadSummary()])
}

async function confirmDeleteExpense() {
  if (!deleteTarget.value) return
  try {
    await deleteExpense(deleteTarget.value.id)
    toast.success('Expense deleted')
    deleteTarget.value = null
    await Promise.all([loadExpenses(), loadSummary()])
  } catch {
    toast.error('Could not delete this expense')
  }
}

// Hero figures: ticket sales are what is left of the Collection after donations and sponsorships.
// The four sections of the page, one visible at a time (the PDF report stacks them all).
type AccTab = 'overview' | 'collections' | 'expenses' | 'donations'
const activeTab = ref<AccTab>('overview')
const accTabs = computed(() => [
  { id: 'overview' as const, label: 'Overview', count: null },
  { id: 'collections' as const, label: 'Collections', count: collTotal.value },
  { id: 'expenses' as const, label: 'Expenses', count: expTotal.value + feeLines.value.length },
  { id: 'donations' as const, label: 'Donations & Sponsorships', count: conTotal.value },
])

const ticketSales = computed(() =>
  Math.max(0, (summary.value?.collection_total ?? 0) - (summary.value?.donations_total ?? 0) - (summary.value?.sponsorships_total ?? 0)),
)
const share = (amount: number) => {
  const total = summary.value?.collection_total ?? 0
  return total > 0 ? Math.round((amount / total) * 1000) / 10 : 0
}
const maxTypeCount = computed(() => Math.max(1, ...(summary.value?.tickets_by_type ?? []).map((r) => r.count)))

const couponTotals = computed(() => {
  const rows = summary.value?.coupon_usage ?? []
  return rows.reduce(
    (t, r) => ({
      orders: t.orders + r.orders_count,
      tickets: t.tickets + r.tickets_count,
      gross: t.gross + r.gross_total,
      discount: t.discount + r.discount_total,
      paid: t.paid + r.paid_total,
    }),
    { orders: 0, tickets: 0, gross: 0, discount: 0, paid: 0 },
  )
})
</script>

<template>
  <div class="ds-scope acc-page" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div class="acc-head" :class="{ 'acc-head-draft': phase === 'draft' }" style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console · Accounting</span>
        <div class="acc-title-row">
          <h1 class="ds-display ds-display-s">{{ summary?.event.title ?? 'Event accounting' }}</h1>
          <span v-if="phase" class="ds-badge event-phase" :class="EVENT_PHASE_BADGE[phase]">{{ EVENT_PHASE_LABEL[phase] }}</span>
        </div>
      </div>
      <div class="acc-header-actions">
        <BaseButton
          type="button"
          variant="secondary"
          size="sm"
          class="download-report"
          :disabled="downloadingReport || summaryLoading || summaryError"
          title="One PDF with everything on this page: figures, breakdowns, coupons, all collections and all expenses (with what each order bought if Show details is ticked)"
          @click="handleDownloadReport"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m7 10 5 5 5-5" /><path d="M12 15V3" /></svg>
          {{ downloadingReport ? 'Preparing…' : 'Download PDF report' }}
        </BaseButton>
        <BaseButton type="button" to="/admin/accounting" variant="secondary" size="sm">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
          Back
        </BaseButton>
      </div>
    </div>

    <hr class="ds-section-line" />

    <BaseLoadingState v-if="summaryLoading" label="Loading accounting summary…" />
    <div v-else-if="summaryError" class="ds-alert ds-alert-danger"><div>Couldn't load the accounting summary. Please try again shortly.</div></div>
    <template v-else-if="summary">
      <!-- Hero: the net result, how it adds up, and the four headline figures -->
      <div class="acc-hero">
        <div class="acc-hero-left">
        <div class="ds-card acc-net">
          <p class="acc-small">Net revenue</p>
          <div class="acc-net-value">{{ formatPriceRounded(summary.net_total) }}</div>
          <p class="acc-eq">
            <strong>{{ formatPriceRounded(summary.collection_total) }}</strong> collected
            <span>−</span>
            <strong>{{ formatPriceRounded(summary.expenses_total) }}</strong> expenses
          </p>
          <div v-if="summary.collection_total > 0" class="acc-bar" role="img" aria-label="Where the collection comes from">
            <i class="acc-seg-tickets" :style="{ width: `${share(ticketSales)}%` }"></i>
            <i class="acc-seg-donations" :style="{ width: `${share(summary.donations_total)}%` }"></i>
            <i class="acc-seg-sponsors" :style="{ width: `${share(summary.sponsorships_total)}%` }"></i>
          </div>
          <div class="acc-legend">
            <span class="acc-legend-tickets">Ticket sales {{ formatPriceRounded(ticketSales) }}</span>
            <span class="acc-legend-donations">Donations {{ formatPriceRounded(summary.donations_total) }}</span>
            <span class="acc-legend-sponsors">Sponsorships {{ formatPriceRounded(summary.sponsorships_total) }}</span>
          </div>
        </div>
        <div class="ds-card acc-schedule">
          <p class="acc-small">Event schedule</p>
          <div class="acc-schedule-kind">{{ schedule.kind }}</div>
          <p class="acc-kpi-note">{{ schedule.dates }}</p>
        </div>
        </div>
        <div class="acc-kpis">
          <div class="ds-card acc-kpi">
            <p class="acc-small">Collection</p>
            <div class="acc-kpi-value">{{ formatPriceRounded(summary.collection_total) }}</div>
            <p class="acc-kpi-note">Incl. donations &amp; Sponsorships</p>
          </div>
          <div class="ds-card acc-kpi">
            <p class="acc-small">Expenses</p>
            <div class="acc-kpi-value">{{ formatPriceRounded(summary.expenses_total) }}</div>
            <p class="acc-kpi-note">{{ summary.recorded_expenses_total > 0 ? 'Recorded + provider fees' : 'Provider fees only' }}</p>
          </div>
          <div v-if="ticketsOn" class="ds-card acc-kpi">
            <p class="acc-small">Tickets sold</p>
            <div class="acc-kpi-value">{{ summary.tickets_sold }}</div>
            <p class="acc-kpi-note">{{ couponTotals.tickets }} used a coupon</p>
          </div>
          <div class="ds-card acc-kpi">
            <p class="acc-small">Coupon discounts</p>
            <div class="acc-kpi-value">{{ couponTotals.discount > 0 ? '−' : '' }}{{ formatPriceRounded(couponTotals.discount) }}</div>
            <p class="acc-kpi-note">On {{ formatPriceRounded(couponTotals.gross) }} list price</p>
          </div>
          <div class="ds-card acc-kpi donations-card">
            <p class="acc-small">Donations</p>
            <div class="acc-kpi-value">{{ formatPriceRounded(summary.donations_total) }}</div>
            <p class="acc-kpi-note">Received, fees absorbed</p>
          </div>
          <div class="ds-card acc-kpi sponsorships-card">
            <p class="acc-small">Sponsorships</p>
            <div class="acc-kpi-value">{{ formatPriceRounded(summary.sponsorships_total) }}</div>
            <p class="acc-kpi-note">{{ summary.pending_contributions ? `${summary.pending_contributions} pending, not counted` : 'Received' }}</p>
          </div>
        </div>
      </div>

      <div v-if="checkinOn && summary.tickets_expected > 0" class="ds-card checkin-card acc-checkin">
        <div class="acc-checkin-main">
          <p class="acc-small">Check-in rate</p>
          <div class="ds-progress-track">
            <div class="ds-progress-bar ds-progress-bar-primary" :style="{ width: `${checkinRate}%` }"></div>
          </div>
        </div>
        <div class="acc-checkin-side">
          <span class="acc-checkin-rate">{{ checkinRate }}%</span>
          <span class="ds-meta">{{ summary.tickets_checked_in }} of {{ summary.tickets_expected }} tickets</span>
        </div>
      </div>

      <div class="acc-def">
        <p class="ds-eyebrow">How these numbers are calculated</p>
        <ul class="ds-meta acc-formulas">
          <li><strong>Collection</strong> = what customers paid in total: paid order totals (Cash + Vipps QR + Vipps App + free orders, each after its coupon discount) + convenience fees + donations and Sponsorships received</li>
          <li><strong>Expenses</strong> = all expenses entered for this event + the payment providers' processing fees</li>
          <li><strong>Net</strong> = Collection − Expenses</li>
          <li><strong>Tickets sold</strong> = tickets on paid orders, all ticket types, free and coupon tickets included</li>
          <li>Pending, rejected, cancelled and refunded orders are not counted.</li>
        </ul>
      </div>

    </template>

    <nav class="ds-tabs acc-tabs" role="tablist" aria-label="Accounting sections">
      <button
        v-for="tab in accTabs"
        :key="tab.id"
        type="button"
        role="tab"
        class="ds-tab"
        :class="{ 'ds-tab-active': activeTab === tab.id }"
        :aria-selected="activeTab === tab.id"
        :data-tab="tab.id"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}<span v-if="tab.count !== null" class="acc-tab-count">{{ tab.count }}</span>
      </button>
    </nav>

    <div v-if="summary" v-show="activeTab === 'overview'" class="acc-pane">
      <div v-if="summary.tickets_by_type.length || summary.tickets_by_sale_mode.length || summary.top_expense_categories.length || summary.coupon_usage.length" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <div v-if="summary.tickets_by_type.length || summary.tickets_by_sale_mode.length || summary.top_expense_categories.length || summary.coupon_usage.length" class="acc-overview">
          <div v-if="ticketsOn && summary.tickets_by_type.length" class="ds-card acc-card">
            <p class="acc-card-title">Tickets by type</p>
            <ul class="acc-rows acc-list">
              <li v-for="row in summary.tickets_by_type" :key="`${row.name}-${row.valid_on}`" class="acc-type-row">
                <span class="ds-meta">{{ row.name }}<template v-if="row.valid_on"> · {{ formatTicketDayShort(row.valid_on) }}</template></span>
                <span class="ds-body acc-count">{{ row.count }}</span>
                <span class="acc-meter"><i :style="{ width: `${(row.count / maxTypeCount) * 100}%` }"></i></span>
              </li>
            </ul>
          </div>

          <div class="acc-pair">
            <div v-if="ticketsOn && summary.tickets_by_sale_mode.length" class="ds-card acc-card">
              <p class="acc-card-title">Tickets by Channels</p>
              <ul class="acc-rows acc-list">
                <li v-for="row in summary.tickets_by_sale_mode" :key="row.provider" class="acc-channel-row">
                  <span class="ds-body" style="font-weight: 600">{{ providerLabel(row.provider) }}</span>
                  <span class="ds-body acc-count">{{ row.count }}</span>
                  <span class="acc-channel-sub">
                    <span class="channel-amount">Amount {{ formatPrice(row.amount ?? 0) }}</span>
                    <span v-if="commissionFor(row.provider)" class="channel-commission"> · Commission {{ formatPrice(commissionFor(row.provider)) }}</span>
                  </span>
                </li>
              </ul>
              <p v-if="summary.processing_fees_total" class="provider-commissions acc-total-line">
                <span>Provider commissions</span>
                <span>{{ formatPrice(summary.processing_fees_total) }}</span>
              </p>
            </div>

            <div v-if="summary.coupon_usage.length" class="ds-card acc-card coupons-glance">
              <p class="acc-card-title">Coupons at a glance</p>
              <p class="acc-glance-row"><span>Coupon orders</span><strong>{{ couponTotals.orders }}</strong></p>
              <p class="acc-glance-row"><span>Revenue given up</span><strong>{{ formatPriceRounded(couponTotals.discount) }}</strong></p>
              <p class="acc-glance-row"><span>Still paid by customers</span><strong>{{ formatPriceRounded(couponTotals.paid) }}</strong></p>
            </div>

            <div v-if="summary.top_expense_categories.length" class="ds-card acc-card">
              <p class="acc-card-title">Top Expenses</p>
              <ul class="acc-rows acc-list">
                <li v-for="row in summary.top_expense_categories" :key="row.category" class="acc-glance-row">
                  <span class="ds-meta">{{ categoryLabel(row.category) }}</span>
                  <strong>{{ formatPrice(row.amount) }}</strong>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <h2 v-if="summary.coupon_usage.length" class="ds-title acc-section-title">Coupon usage</h2>
        <div v-if="summary.coupon_usage.length" class="ds-table-wrap coupon-usage">
          <div class="ds-table-scroll">
            <table class="ds-table" style="min-width: 640px">
              <thead>
                <tr>
                  <th>Coupon</th>
                  <th data-align="right">Orders</th>
                  <th>Used</th>
                  <th data-align="right">Before discount</th>
                  <th data-align="right">Discount</th>
                  <th data-align="right">Paid</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="row in summary.coupon_usage" :key="row.coupon_code">
                <tr class="coupon-main" :class="{ 'coupon-main--open': row.by_ticket_type.length }">
                  <td data-emphasis>
                    <span class="coupon-code">{{ row.coupon_code }}</span>
                    <span v-if="row.discount_percent !== null" class="ds-badge ds-badge-accent coupon-pill">{{ row.discount_percent }}% off</span>
                    <span v-if="row.is_active === false" class="ds-badge ds-badge-neutral coupon-pill">Retired</span>
                  </td>
                  <td data-align="right">{{ row.orders_count }}</td>
                  <td class="coupon-used">
                    {{ row.tickets_count }}<span v-if="row.max_redemptions !== null"> / {{ row.max_redemptions }}</span>
                    <span v-if="row.max_redemptions" class="coupon-meter"><i :style="{ width: `${Math.min(100, (row.tickets_count / row.max_redemptions) * 100)}%` }"></i></span>
                  </td>
                  <td data-align="right">{{ formatPrice(row.gross_total) }}</td>
                  <td data-align="right" class="coupon-discount">−{{ formatPrice(row.discount_total) }}</td>
                  <td data-align="right" style="font-weight: 600">{{ formatPrice(row.paid_total) }}</td>
                </tr>
                <tr v-if="row.by_ticket_type.length" class="coupon-types">
                  <td colspan="6">
                    <ul class="coupon-types-list">
                      <li v-for="t in row.by_ticket_type" :key="`${t.name}-${t.valid_on}`">
                        <span class="ds-meta">{{ t.name }}<template v-if="t.valid_on"> · {{ formatTicketDayShort(t.valid_on) }}</template></span>
                        <span class="ds-body" style="font-weight: 600">{{ t.count }}</span>
                      </li>
                    </ul>
                  </td>
                </tr>
                </template>
              </tbody>
              <tfoot v-if="summary.coupon_usage.length > 1">
                <tr class="coupon-total">
                  <td data-emphasis>All coupons</td>
                  <td data-align="right">{{ couponTotals.orders }}</td>
                  <td>{{ couponTotals.tickets }}</td>
                  <td data-align="right">{{ formatPrice(couponTotals.gross) }}</td>
                  <td data-align="right" class="coupon-discount">−{{ formatPrice(couponTotals.discount) }}</td>
                  <td data-align="right">{{ formatPrice(couponTotals.paid) }}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>
    </div>

    <section v-if="ticketsOn" v-show="activeTab === 'collections'" class="acc-pane" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
      <div class="acc-section-head">
        <h2 class="ds-title">Collections</h2>
        <BaseButton
          v-if="collections.length > 0"
          type="button"
          variant="secondary"
          size="sm"
          class="export-buyers"
          :disabled="exportingBuyers"
          title="Everyone who paid for tickets to this event, buyers and individual tickets (follows the filters above)"
          @click="handleExportBuyers"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m7 10 5 5 5-5" /><path d="M12 15V3" /></svg>
          {{ exportingBuyers ? 'Exporting…' : 'Export collections to Excel' }}
        </BaseButton>
      </div>
      <div v-if="collections.length > 0 || collFiltersActive" class="ds-toolbar ds-toolbar-fit">
        <div style="flex: 1 1 100%; display: flex; align-items: center; gap: var(--ds-space-4)">
          <BaseSearchField v-model="collSearch" size="sm" style="flex: 1 1 auto; min-width: 0" placeholder="Order number, name, or email" @keyup.enter="loadCollections" />
          <label class="ds-checkbox" style="flex: 0 0 auto; align-items: center">
            <input v-model="showCollDetails" type="checkbox" />
            <span class="ds-checkbox-box">✓</span>
            <span class="ds-checkbox-label">Show details</span>
          </label>
        </div>
        <BaseMultiSelect v-model="collMethod" size="sm" class="ds-toolbar-select-wide" :options="collMethodOptions" all-label="All payment methods" aria-label="Filter by payment method" highlight-active />
        <BaseMultiSelect v-if="collCouponOptions.length > 0" v-model="collCoupon" size="sm" class="ds-toolbar-select-wide" :options="collCouponOptions" all-label="All coupons" aria-label="Filter by coupon" highlight-active />
        <BaseMultiSelect v-model="collTicketType" size="sm" class="ds-toolbar-select-wide" :options="collTicketTypeOptions" all-label="All ticket types" aria-label="Filter by ticket type" highlight-active />
      </div>
      <BaseLoadingState v-if="collectionsLoading" label="Loading collections…" />
      <div v-else-if="collectionsError" class="ds-alert ds-alert-danger"><div>Couldn't load collections. Please try again shortly.</div></div>
      <BaseEmptyState v-else-if="collections.length === 0 && collFiltersActive" title="No collections match this filter or search" description="Clear the search or a filter to see every paid order again." />
      <BaseEmptyState v-else-if="collections.length === 0" title="No collections yet" description="Paid ticket orders for this event will show up here." />
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Reference</th>
                <th>Payer</th>
                <th>Method</th>
                <th data-align="right">Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody v-for="item in collItems" :key="item.id">
              <tr>
                <td style="white-space: nowrap">{{ formatEventDate(item.date) }}</td>
                <td data-emphasis style="white-space: nowrap"><router-link :to="`/admin/orders/${item.id}`" class="ds-ref-link" :aria-label="`Open order ${item.order_number}`">{{ item.order_number }}</router-link></td>
                <td>{{ item.customer_name }}</td>
                <td>
                  <template v-if="item.payment_method">{{ providerLabel(item.payment_method) }}</template>
                  <template v-else-if="item.coupon_code">
                    Coupon
                    <div class="ds-caption">{{ item.coupon_code }}</div>
                  </template>
                  <template v-else>{{ providerLabel(null) }}</template>
                </td>
                <td data-align="right">{{ formatPrice(item.amount) }}</td>
                <td><span class="ds-badge" :class="statusTone(item.payment_status)">{{ paymentStatusLabel(item.payment_status) }}</span></td>
              </tr>
              <tr v-if="showCollDetails" class="collection-tickets-row">
                <td colspan="6" class="ds-meta" style="padding-top: 0; white-space: normal">
                  <div v-for="line in item.tickets" :key="line" style="margin-left: 2rem">{{ line }}</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <PaginationBar v-model:page="collPage" :total-pages="collTotalPages" :total="collTotal" />
    </section>

    <section v-show="activeTab === 'expenses'" class="acc-pane" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
      <div class="acc-section-head">
        <h2 class="ds-title">Expenses</h2>
        <div class="acc-section-actions">
          <BaseMultiSelect v-model="categoryFilter" size="sm" :options="expenseCategories" all-label="All categories" aria-label="Filter by category" highlight-active />
          <BaseButton
            v-if="expenses.length > 0"
            type="button"
            variant="secondary"
            size="sm"
            class="export-expenses"
            :disabled="exportingExpenses"
            title="The expenses recorded for this event, with a total (only the chosen category if one is selected)"
            @click="handleExportExpenses"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m7 10 5 5 5-5" /><path d="M12 15V3" /></svg>
            {{ exportingExpenses ? 'Exporting…' : 'Export expenses to Excel' }}
          </BaseButton>
          <BaseButton type="button" variant="secondary" size="sm" class="add-expense" @click="openAddExpense">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
            Add expense
          </BaseButton>
        </div>
      </div>

      <BaseLoadingState v-if="expensesLoading" label="Loading expenses…" />
      <div v-else-if="expensesError" class="ds-alert ds-alert-danger"><div>Couldn't load expenses. Please try again shortly.</div></div>
      <BaseEmptyState v-else-if="expenses.length === 0 && !showFeeLines" title="No expenses yet" description="Add an expense to start tracking spend for this event." />
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th>Category</th>
                <th>Vendor</th>
                <th data-align="right">Amount</th>
                <th>Receipt</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="line in (showFeeLines ? feeLines : [])" :key="`fee-${line.provider}`" class="processing-fee-line">
                <td>—</td>
                <td data-emphasis>{{ providerLabel(line.provider) }} processing fees</td>
                <td><span class="ds-badge ds-badge-neutral">Payment fees</span></td>
                <td>{{ providerLabel(line.provider) }}</td>
                <td data-align="right">{{ formatPrice(line.amount) }}</td>
                <td>—</td>
                <td></td>
              </tr>
              <tr v-for="expense in expItems" :key="expense.id">
                <td>{{ formatEventDate(expense.date) }}</td>
                <td data-emphasis>{{ expense.description }}</td>
                <td><span class="ds-badge ds-badge-neutral">{{ categoryLabel(expense.category) }}</span></td>
                <td>{{ expense.vendor ?? '—' }}</td>
                <td data-align="right">{{ formatPrice(expense.amount) }}</td>
                <td>
                  <BaseIconButton
                    v-if="expense.receipt_url"
                    variant="bare"
                    size="sm"
                    :label="`View receipt for ${expense.description}`"
                    @click="openReceipt(expense.receipt_url)"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg>
                  </BaseIconButton>
                  <span v-else>—</span>
                </td>
                <td data-align="right">
                  <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                    <BaseIconButton variant="bare" size="sm" :label="`View ${expense.description}`" @click="openViewExpense(expense)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></svg>
                    </BaseIconButton>
                    <BaseIconButton variant="bare" size="sm" :label="`Edit ${expense.description}`" @click="openEditExpense(expense)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                    </BaseIconButton>
                    <BaseIconButton
                      variant="danger"
                      type="button"
                      size="sm"
                      :label="`Delete ${expense.description}`"
                      @click="deleteTarget = expense"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                    </BaseIconButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <PaginationBar v-model:page="expPage" :total-pages="expTotalPages" :total="expTotal" />
    </section>

    <section v-show="activeTab === 'donations'" class="acc-pane" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
      <div class="acc-section-head">
        <h2 class="ds-title">
          Donations &amp; Sponsorships
          <span v-if="summary?.pending_contributions" class="ds-badge ds-badge-accent pending-contributions" style="vertical-align: middle">{{ summary.pending_contributions }} pending</span>
        </h2>
        <div class="acc-section-actions">
          <BaseMultiSelect v-model="kindFilter" size="sm" :options="KIND_FILTER_OPTIONS" all-label="All types" aria-label="Filter by type" highlight-active />
          <BaseButton type="button" variant="secondary" size="sm" class="add-contribution" @click="openAddContribution">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
            Add donation / Sponsorship
          </BaseButton>
        </div>
      </div>

      <BaseLoadingState v-if="contributionsLoading" label="Loading donations and Sponsorships…" />
      <div v-else-if="contributionsError" class="ds-alert ds-alert-danger"><div>Couldn't load donations and Sponsorships. Please try again shortly.</div></div>
      <BaseEmptyState v-else-if="contributions.length === 0" title="Nothing recorded yet" description="Add a donation or a Sponsorship received for this event; it is counted in the Collection." />
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>From</th>
                <th>Type</th>
                <th>Received by</th>
                <th>Status</th>
                <th data-align="right">Amount</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in conItems" :key="c.id">
                <td>{{ formatEventDate(c.date) }}</td>
                <td data-emphasis>
                  {{ c.name }}
                  <span v-if="c.contact_name || c.email || c.phone" class="ds-meta contribution-contact" style="display: block; font-weight: 400">{{ [c.contact_name, c.email, c.phone].filter(Boolean).join(' · ') }}</span>
                  <span v-if="c.requirements" class="ds-meta contribution-requirements" style="display: block; font-weight: 400">Wants: {{ c.requirements }}</span>
                </td>
                <td><span class="ds-badge ds-badge-neutral">{{ c.kind === 'sponsorship' ? 'Sponsorship' : 'Donation' }}</span></td>
                <td>{{ c.payment_method ? providerLabel(c.payment_method) : '—' }}</td>
                <td><span class="ds-badge" :class="c.status === 'paid' ? 'ds-badge-success' : c.status === 'pending' ? 'ds-badge-accent' : 'ds-badge-neutral'">{{ CONTRIBUTION_STATUS[c.status] ?? c.status }}</span></td>
                <td data-align="right">{{ c.amount != null ? formatPrice(c.amount) : '—' }}</td>
                <td data-align="right">
                  <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                    <BaseIconButton v-if="c.status === 'pending'" variant="success" size="sm" :label="`Mark ${c.name} as received`" class="mark-received" @click="markReceived(c)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
                    </BaseIconButton>
                    <BaseIconButton variant="bare" size="sm" :label="`Edit ${c.name}`" @click="openEditContribution(c)">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.854.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z" /></svg>
                    </BaseIconButton>
                    <BaseIconButton variant="danger" type="button" size="sm" :label="`Delete ${c.name}`" @click="deleteContributionTarget = c">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
                    </BaseIconButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <PaginationBar v-model:page="conPage" :total-pages="conTotalPages" :total="conTotal" />
    </section>

    <AccountingContributionModal
      v-model="showContributionModal"
      :event-id="eventId"
      :contribution="contributionTarget"
      @saved="onContributionSaved"
    />

    <BaseModal :model-value="!!deleteContributionTarget" title="Delete entry" @update:model-value="deleteContributionTarget = null">
      <p class="ds-body">Delete the {{ deleteContributionTarget?.kind === 'sponsorship' ? 'Sponsorship' : 'donation' }} from "{{ deleteContributionTarget?.name }}"? It will no longer count in the Collection. This cannot be undone.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="deleteContributionTarget = null">Cancel</BaseButton>
        <BaseButton type="button" variant="danger" @click="confirmDeleteContribution">Delete</BaseButton>
      </div>
    </BaseModal>

    <AccountingExpenseModal
      v-model="showExpenseModal"
      :event-id="eventId"
      :expense="editTarget"
      @saved="onExpenseSaved"
    />

    <BaseModal :model-value="!!deleteTarget" title="Delete expense" @update:model-value="deleteTarget = null">
      <p class="ds-body">Delete the expense "{{ deleteTarget?.description }}"? This cannot be undone.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="deleteTarget = null">Cancel</BaseButton>
        <BaseButton type="button" @click="confirmDeleteExpense" variant="danger">Delete</BaseButton>
      </div>
    </BaseModal>

    <AccountingReceiptModal v-model="showReceiptViewer" :url="viewingReceiptUrl" />

    <AccountingExpenseViewModal v-model="showViewModal" :expense="viewTarget" @edit="editFromViewModal" />
  </div>
</template>

<style scoped>
.acc-page { container-type: inline-size; max-width: 1120px; }
/* Compact scale for this page (design: 14px body, 13px tables, 32px figures) */
.acc-page :deep(.ds-title) { font-size: 22px; }
.acc-page :deep(.ds-display-s) { font-size: clamp(24px, 2.6vw, 30px); }
.acc-page :deep(.ds-card) { padding: 18px 20px; }
.acc-page :deep(.ds-table) { font-size: 13.5px; }
.acc-page :deep(.ds-table th) { padding: 9px 12px; }
.acc-page :deep(.ds-table td) { padding: 9px 12px; }
.acc-page :deep(.ds-table th), .acc-page :deep(.ds-table td) { white-space: nowrap; }
.acc-page .acc-formulas { font-size: 13px; }
.acc-tabs { flex-wrap: wrap; row-gap: 0; gap: var(--ds-space-5); }
.acc-tabs .ds-tab { white-space: nowrap; }
.acc-tab-count { margin-left: 6px; font-weight: 400; color: var(--ds-text-muted); }
.acc-section-title { margin: var(--ds-space-2) 0 0; }
.coupon-used { white-space: nowrap; }
.coupon-meter { display: block; height: 4px; border-radius: 4px; background: var(--ds-border-hairline); margin-top: 4px; min-width: 70px; }
.coupon-meter i { display: block; height: 100%; border-radius: 4px; background: var(--ds-status-warning, var(--ds-action-primary)); }
/* Hero (Event Accounting Redesign): the net result, its make-up and six headline figures */
.acc-hero { display: grid; grid-template-columns: 1.15fr 0.5fr 0.5fr; gap: var(--ds-space-3); align-items: stretch; }
/* One shared grid: Net spans the first two rows (= the two top rows of figure cards), Event schedule is the
   third row (= the Donations / Sponsorships row), so the left and right heights always line up. */
.acc-hero-left, .acc-kpis { display: contents; }
.acc-hero .acc-net { grid-column: 1; grid-row: 1 / span 2; }
.acc-hero .acc-schedule { grid-column: 1; grid-row: 3; }
@container (max-width: 760px) {
  .acc-hero { grid-template-columns: 1fr 1fr; }
  .acc-hero .acc-net, .acc-hero .acc-schedule { grid-column: 1 / -1; grid-row: auto; }
}
.acc-small { margin: 0; font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ds-text-muted); }
.acc-hero-left .acc-net { padding: 14px 20px !important; gap: 6px; }
.acc-schedule { display: flex; flex-direction: column; gap: 2px; padding: 14px 20px !important; }
.acc-schedule-kind { font-family: var(--ds-font-display); font-size: 1.25rem; line-height: 1.25; color: var(--ds-text-heading); }
.acc-page .acc-net.ds-card { background: var(--ds-paper-300); border-color: var(--ds-paper-300); }
html.dark .acc-page .acc-net.ds-card { background: var(--ds-palm-800); border-color: var(--ds-palm-800); }
.acc-net { display: flex; flex-direction: column; gap: var(--ds-space-2); justify-content: center; }
.acc-net-value { font-family: var(--ds-font-display); font-size: clamp(2rem, 3.2vw, 2.7rem); line-height: 1.1; color: var(--ds-status-success-ink); white-space: nowrap; }
.acc-eq { margin: 0; font-size: 13px; color: var(--ds-text-muted); display: flex; gap: var(--ds-space-2); flex-wrap: nowrap; white-space: nowrap; align-items: center; }
.acc-eq strong { color: var(--ds-text-heading); font-weight: 600; }
.acc-bar { display: flex; height: 8px; border-radius: 9px; overflow: hidden; background: var(--ds-border-hairline); margin-top: var(--ds-space-2); }
.acc-bar i { display: block; height: 100%; }
.acc-seg-tickets { background: var(--ds-status-success); }
.acc-seg-donations { background: var(--ds-action-primary); }
.acc-seg-sponsors { background: var(--ds-border-strong); }
.acc-legend { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--ds-text-muted); }
@container (max-width: 560px) { .acc-eq { flex-wrap: wrap; white-space: normal; } }
.acc-legend span::before { content: ''; display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; background: var(--c); }
.acc-legend-tickets { --c: var(--ds-status-success); }
.acc-legend-donations { --c: var(--ds-action-primary); }
.acc-legend-sponsors { --c: var(--ds-border-strong); }
.acc-kpi { display: flex; flex-direction: column; gap: 2px; padding: 14px 18px !important; }
.acc-kpi-value { font-family: var(--ds-font-display); font-size: clamp(1.3rem, 2vw, 1.7rem); line-height: 1.2; color: var(--ds-text-heading); white-space: nowrap; }
.acc-kpi-note { margin: 0; font-size: 11px; line-height: 1.3; color: var(--ds-text-faint); }
.acc-checkin { display: flex; flex-direction: row; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: nowrap; }
@container (max-width: 560px) { .acc-checkin { flex-wrap: wrap; } }
.acc-checkin-main { flex: 0 1 380px; min-width: 200px; display: flex; flex-direction: column; gap: var(--ds-space-2); }
.acc-checkin-side { margin-left: auto; display: flex; align-items: baseline; gap: var(--ds-space-3); white-space: nowrap; }
.acc-checkin-rate { font-family: var(--ds-font-display); font-size: 1.6rem; color: var(--ds-text-heading); }
.acc-def .acc-formulas { margin: var(--ds-space-2) 0 0; padding-left: var(--ds-space-5); }
/* Overview: tickets by type on the left, channels / coupons / top expenses stacked on the right */
.acc-overview { display: flex; flex-direction: column; gap: var(--ds-space-4); }
.acc-pair { display: grid; grid-template-columns: 1fr 1fr; gap: var(--ds-space-4); align-items: start; }
@container (max-width: 760px) { .acc-pair { grid-template-columns: 1fr; } }
.acc-card { display: flex; flex-direction: column; gap: var(--ds-space-2); }
.acc-card-title { margin: 0 0 var(--ds-space-1); font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ds-text-primary); font-weight: 600; }
.acc-list { list-style: none; padding: 0; margin: 0; }
.acc-type-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px var(--ds-space-3); align-items: center; padding: 6px 0; font-size: 13.5px; }
.acc-count { font-weight: 600; text-align: right; }
.acc-meter { grid-column: 1 / -1; height: 5px; border-radius: 5px; background: var(--ds-border-hairline); }
.acc-meter i { display: block; height: 100%; border-radius: 5px; background: var(--ds-action-primary); opacity: 0.75; }
.acc-channel-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; padding: 6px 0; font-size: 13.5px; }
.acc-channel-sub { grid-column: 1 / -1; font-size: 12px; color: var(--ds-text-faint); }
.acc-channel-sub .channel-amount { font-size: 15px; font-weight: 400; color: var(--ds-text-body); }
.acc-total-line { margin: 0; display: flex; justify-content: space-between; padding-top: var(--ds-space-2); border-top: 1px solid var(--ds-border-hairline); font-weight: 600; font-size: 13.5px; }
.acc-glance-row { margin: 0; display: flex; justify-content: space-between; padding: 3px 0; font-size: 13.5px; }
.coupon-code { margin-right: var(--ds-space-2); }
.coupon-main--open td { border-bottom: none; padding-bottom: var(--ds-space-1); }
.coupon-types td { padding-top: 0; white-space: normal; }
.coupon-types-list { list-style: none; margin: 0; padding: 0 0 0 var(--ds-space-4); }
.coupon-types-list li { display: flex; justify-content: space-between; gap: var(--ds-space-4); padding: var(--ds-space-1) 0; }
.coupon-types-list li + li { border-top: 1px solid var(--ds-border-hairline); }
.coupon-pill { margin: 2px 6px 2px 0; font-weight: 400; }
.coupon-discount { color: var(--ds-status-success-ink); white-space: nowrap; }
.coupon-total td { border-top: 1px solid var(--ds-border-strong); font-weight: 600; background: var(--ds-surface-sunken); }
.acc-header-actions { display: flex; gap: var(--ds-space-2); flex-wrap: wrap; justify-content: flex-end; }
.acc-divider {
  width: 100%;
  border: none;
  border-top: 1px solid var(--ds-border-hairline);
  margin: 0;
}
.acc-rows > li + li,
.acc-row + .acc-row {
  border-top: 1px solid var(--ds-border-hairline);
}
/* Section title on the left, its actions on the right; wraps below the title on narrow screens. */
.acc-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-4);
  flex-wrap: wrap;
}
.acc-section-actions {
  display: flex;
  align-items: center;
  gap: var(--ds-space-3);
  flex-wrap: wrap;
}
.acc-category-filter {
  min-width: 180px;
}
@media (max-width: 640px) {
  .acc-section-head {
    align-items: stretch;
    flex-direction: column;
    gap: var(--ds-space-3);
  }
  /* Filter on its own full-width line, the buttons share the next one. */
  .acc-category-filter {
    flex: 1 1 100%;
    min-width: 0;
  }
  .acc-section-actions > :deep(button),
  .acc-section-head > :deep(button) {
    flex: 1 1 auto;
    justify-content: center;
  }
}

.acc-formulas { margin: 0; padding-left: 1.2rem; list-style: disc; }
.acc-title-row { display: flex; align-items: center; flex-wrap: wrap; gap: var(--ds-space-3); }
.acc-title-row h1 { margin: 0; }
.event-phase { flex-shrink: 0; }

/* Same draft treatment as the Accounting events list: a faint diagonal DRAFT watermark behind the
   header so an unpublished event's books are unmistakable. */
.acc-head-draft { position: relative; }
.acc-head-draft::after {
  content: 'DRAFT';
  position: absolute;
  top: 50%;
  left: 50%;
  font: 800 64px / 1 var(--ds-font-body);
  letter-spacing: 0.18em;
  white-space: nowrap;
  color: var(--ds-text-primary);
  opacity: 0.08;
  transform: translate(-50%, -50%) rotate(-8deg);
  pointer-events: none;
  user-select: none;
}
.acc-head-draft > * { position: relative; z-index: 1; }
</style>
