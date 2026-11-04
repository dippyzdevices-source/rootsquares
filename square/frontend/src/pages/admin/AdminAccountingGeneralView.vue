<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import AccountingExpenseModal from './AccountingExpenseModal.vue'
import AccountingExpenseViewModal from './AccountingExpenseViewModal.vue'
import AccountingReceiptModal from './AccountingReceiptModal.vue'
import AccountingIncomeModal from './AccountingIncomeModal.vue'
import {
  deleteExpense,
  deleteManualIncome,
  exportGeneralBook,
  exportGeneralReport,
  fetchGeneralBudget,
  setGeneralBudget,
  setGeneralIncomeTarget,
  copyGeneralBudget,
  type GeneralBudget,
  fetchEventExpenses,
  fetchGeneralIncome,
  fetchGeneralSummary,
  ValidationError,
  type Expense,
  type GeneralIncomeRow,
  type GeneralSummary,
} from '../../services/adminAccountingApi'
import { moduleEnabled } from '../../services/modules'
import { formatPrice, formatPriceRounded } from '../../utils/money'
import { downloadBlob } from '../../utils/download'
import { formatEventDate } from '../../utils/date'
import { useLookup } from '../../composables/useLookup'
import { useToast } from '../../composables/useToast'

// The general book of Accounting (W14-R15): costs that belong to no event, and the money that comes in without one (gifts, membership payments).
// It is the whole of Accounting for a square without the Events module, and one more book next to the events for a square that has them.
const toast = useToast()
const { label: categoryLabel } = useLookup('expense_category')
const eventsOn = moduleEnabled('events')

const year = ref('all') // 'all' or a four-digit year
const yearOptions = computed(() => {
  const now = new Date().getFullYear()
  return [{ value: 'all', label: 'All time' }, ...[0, 1, 2, 3, 4].map((i) => ({ value: String(now - i), label: String(now - i) }))]
})
const range = computed(() => (year.value === 'all' ? {} : { dateFrom: `${year.value}-01-01`, dateTo: `${year.value}-12-31` }))

const summary = ref<GeneralSummary | null>(null)
const income = ref<GeneralIncomeRow[]>([])
const expenses = ref<Expense[]>([])
const loading = ref(true)
const failed = ref(false)

async function load() {
  loading.value = true
  failed.value = false
  try {
    const [s, i, e] = await Promise.all([fetchGeneralSummary(range.value), fetchGeneralIncome(range.value), fetchEventExpenses(null, { perPage: 50, ...range.value })])
    summary.value = s
    income.value = i
    expenses.value = e.items
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(year, load)

const sourceName = (row: GeneralIncomeRow) => (row.source === 'donation' ? 'Gift' : row.source === 'manual' ? 'Added by hand' : 'Membership payment')

const showIncomeModal = ref(false)
const incomeEdit = ref<GeneralIncomeRow | null>(null)
const incomeDelete = ref<GeneralIncomeRow | null>(null)
function addIncome() {
  incomeEdit.value = null
  showIncomeModal.value = true
}
function editIncome(row: GeneralIncomeRow) {
  incomeEdit.value = row
  showIncomeModal.value = true
}
async function confirmDeleteIncome() {
  if (!incomeDelete.value?.id) return
  try {
    await deleteManualIncome(incomeDelete.value.id)
    toast.success('Income deleted')
    incomeDelete.value = null
    await load()
  } catch {
    toast.error('Could not delete this income')
  }
}

const showModal = ref(false)
const editTarget = ref<Expense | null>(null)
const deleteTarget = ref<Expense | null>(null)
const viewTarget = ref<Expense | null>(null)
const showView = ref(false)
const receiptUrl = ref<string | null>(null)
const showReceipt = ref(false)

function add() {
  editTarget.value = null
  showModal.value = true
}
function edit(expense: Expense) {
  editTarget.value = expense
  showModal.value = true
}
function openReceipt(url: string) {
  receiptUrl.value = url
  showReceipt.value = true
}
function openDetails(expense: Expense) {
  viewTarget.value = expense
  showView.value = true
}
function editFromDetails(expense: Expense) {
  showView.value = false
  edit(expense)
}
async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await deleteExpense(deleteTarget.value.id)
    toast.success('Expense deleted')
    deleteTarget.value = null
    await load()
  } catch {
    toast.error('Could not delete this expense')
  }
}
const exportingPdf = ref(false)
async function doExportPdf() {
  exportingPdf.value = true
  try {
    downloadBlob(await exportGeneralReport(range.value), year.value === 'all' ? 'general-accounts-report.pdf' : 'general-accounts-report-' + year.value + '.pdf')
  } catch {
    toast.error('Could not build the PDF')
  } finally {
    exportingPdf.value = false
  }
}

// Yearly budgets (W15-R18): one amount per expense category for the chosen year, shown next to what was spent.
const budget = ref<GeneralBudget | null>(null)
const budgetError = ref('')
async function loadBudget() {
  budgetError.value = ''
  budget.value = null
  if (year.value === 'all') return
  try {
    budget.value = await fetchGeneralBudget(Number(year.value))
  } catch {
    budgetError.value = 'Could not load the budget'
  }
}
async function saveBudget(category: string, event: Event) {
  const raw = (event.target as HTMLInputElement).value.trim()
  const amount = raw === '' ? 0 : Math.round(Number(raw) * 100)
  if (!Number.isFinite(amount) || amount < 0) {
    toast.error('Enter an amount, zero or more')
    return
  }
  try {
    await setGeneralBudget(Number(year.value), category, amount)
    await loadBudget()
  } catch (err) {
    toast.error(err instanceof ValidationError ? Object.values(err.errors)[0] ?? 'Could not save the budget' : 'Could not save the budget')
  }
}
async function saveIncomeTarget(source: string, event: Event) {
  const raw = (event.target as HTMLInputElement).value.trim()
  const amount = raw === '' ? 0 : Math.round(Number(raw) * 100)
  if (!Number.isFinite(amount) || amount < 0) {
    toast.error('Enter an amount, zero or more')
    return
  }
  try {
    await setGeneralIncomeTarget(Number(year.value), source, amount)
    await loadBudget()
  } catch (err) {
    toast.error(err instanceof ValidationError ? Object.values(err.errors)[0] ?? 'Could not save the target' : 'Could not save the target')
  }
}
async function copyLastYear() {
  try {
    const done = await copyGeneralBudget(Number(year.value))
    const count = done.budgets + done.targets
    if (count) toast.success(`Copied ${count} ${count === 1 ? 'amount' : 'amounts'} from ${done.from_year}`)
    else toast.info(`Nothing to copy from ${done.from_year}`)
    await loadBudget()
  } catch {
    toast.error('Could not copy last year')
  }
}
watch(year, loadBudget)
onMounted(loadBudget)

const exporting = ref(false)
async function doExport() {
  exporting.value = true
  try {
    downloadBlob(await exportGeneralBook(range.value), year.value === 'all' ? 'general-accounts.xlsx' : 'general-accounts-' + year.value + '.xlsx')
  } catch {
    toast.error('Could not export')
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console · Accounting</span>
        <h1 class="ds-display ds-display-s">General accounts</h1>
        <p class="ds-intro">Costs that belong to no event, and the money that comes in as gifts, membership payments and income you add yourself.<template v-if="eventsOn"> Each event keeps its own accounts.</template></p>
      </div>
      <div style="display: flex; gap: var(--ds-space-2); align-items: center; flex-wrap: wrap">
        <BaseSelect v-model="year" size="sm" :options="yearOptions" aria-label="Year" highlight-active />
        <BaseButton type="button" variant="secondary" size="sm" class="export-general" :disabled="exporting || loading" @click="doExport">{{ exporting ? 'Exporting…' : 'Export to Excel' }}</BaseButton>
        <BaseButton type="button" variant="secondary" size="sm" class="export-general-pdf" :disabled="exportingPdf || loading" @click="doExportPdf">{{ exportingPdf ? 'Building…' : 'Download PDF' }}</BaseButton>
        <BaseButton v-if="eventsOn" type="button" to="/admin/accounting" variant="secondary" size="sm">Back</BaseButton>
      </div>
    </div>

    <hr class="ds-section-line" />

    <BaseLoadingState v-if="loading" label="Loading the accounts…" />
    <div v-else-if="failed" class="ds-alert ds-alert-danger"><div>Couldn't load the accounts. Please try again shortly.</div></div>
    <template v-else-if="summary">
      <div class="ds-stat-grid ds-stat-grid--3">
        <div class="ds-card">
          <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Income</p>
          <div class="general-income" style="font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); color: var(--ds-text-heading); margin-top: 4px">{{ formatPriceRounded(summary.income.total) }}</div>
          <p v-for="s in summary.income.by_source" :key="s.source" class="ds-meta">{{ s.label }}: {{ formatPrice(s.total) }} ({{ s.count }})</p>
        </div>
        <div class="ds-card">
          <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Expenses</p>
          <div class="general-expenses" style="font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); color: var(--ds-text-heading); margin-top: 4px">{{ formatPriceRounded(summary.expenses.total) }}</div>
          <p v-for="c in summary.expenses.by_category.slice(0, 4)" :key="c.category" class="ds-meta">{{ c.label }}: {{ formatPrice(c.total) }}</p>
        </div>
        <div class="ds-card">
          <p class="ds-eyebrow" style="font-size: var(--ds-text-eyebrow)">Net</p>
          <div class="general-net" style="font-family: var(--ds-font-display); font-size: var(--ds-text-display-s); color: var(--ds-text-primary); margin-top: 4px">{{ formatPriceRounded(summary.net) }}</div>
        </div>
      </div>

      <section style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <div style="display: flex; justify-content: space-between; align-items: center; gap: var(--ds-space-3); flex-wrap: wrap">
          <h2 class="ds-title">Income</h2>
          <BaseButton type="button" variant="secondary" size="sm" class="add-income" @click="addIncome">Add income</BaseButton>
        </div>
        <BaseEmptyState v-if="income.length === 0" title="No income yet" description="Paid gifts and paid membership payments appear here by themselves. Money that came in another way, such as a grant or a hall hire, you add yourself." />
        <div v-else class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table">
              <thead><tr><th>Date</th><th>What</th><th>From</th><th>Reference</th><th data-align="right">Amount</th><th></th></tr></thead>
              <tbody>
                <tr v-for="row in income" :key="row.source + '-' + (row.id ?? row.reference)">
                  <td>{{ formatEventDate(row.date) }}</td>
                  <td><span class="ds-badge ds-badge-neutral">{{ sourceName(row) }}</span></td>
                  <td>{{ row.name ?? '—' }}</td>
                  <td>{{ row.reference ?? '—' }}</td>
                  <td data-align="right">{{ formatPrice(row.amount) }}</td>
                  <td data-align="right">
                    <div v-if="row.source === 'manual'" style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                      <BaseButton type="button" variant="ghost" size="sm" class="edit-income" @click="editIncome(row)">Edit</BaseButton>
                      <BaseButton type="button" variant="ghost" size="sm" class="delete-income" @click="incomeDelete = row">Delete</BaseButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="budget-section" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-3); flex-wrap: wrap">
          <h2 class="ds-title">Budget</h2>
          <BaseButton v-if="year !== 'all'" type="button" variant="secondary" size="sm" class="copy-last-year" @click="copyLastYear">Copy from {{ Number(year) - 1 }}</BaseButton>
        </div>
        <p v-if="year === 'all'" class="ds-meta">Choose a year above to plan what you will spend on each kind of cost, and to see how much is left.</p>
        <div v-else-if="budgetError" class="ds-alert ds-alert-danger"><div>{{ budgetError }}</div></div>
        <div v-else-if="budget" class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table">
              <thead><tr><th>Category</th><th data-align="right">Budget</th><th data-align="right">Spent</th><th data-align="right">Left</th></tr></thead>
              <tbody>
                <tr v-for="row in budget.items" :key="row.category">
                  <td>{{ row.label }}</td>
                  <td data-align="right"><input class="ds-field-input budget-input" type="number" min="0" step="0.01" :value="row.budget ? row.budget / 100 : ''" :aria-label="'Budget for ' + row.label" style="width: 8rem; text-align: right" @change="saveBudget(row.category, $event)" /></td>
                  <td data-align="right">{{ formatPrice(row.spent) }}</td>
                  <td data-align="right" :class="{ 'budget-over': row.budget > 0 && row.remaining < 0 }">{{ row.budget ? formatPrice(row.remaining) : '—' }}</td>
                </tr>
                <tr>
                  <td data-emphasis>Total</td>
                  <td data-align="right" data-emphasis>{{ formatPrice(budget.budget_total) }}</td>
                  <td data-align="right" data-emphasis>{{ formatPrice(budget.spent_total) }}</td>
                  <td data-align="right" data-emphasis>{{ budget.budget_total ? formatPrice(budget.budget_total - budget.spent_total) : '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <template v-if="budget">
          <h3 class="ds-title">Income targets</h3>
          <div class="ds-table-wrap">
            <div class="ds-table-scroll">
              <table class="ds-table">
                <thead><tr><th>Source</th><th data-align="right">Target</th><th data-align="right">Received</th><th data-align="right">Still to raise</th></tr></thead>
                <tbody>
                  <tr v-for="row in budget.income" :key="row.source">
                    <td>{{ row.label }}</td>
                    <td data-align="right"><input class="ds-field-input budget-input" type="number" min="0" step="0.01" :value="row.target ? row.target / 100 : ''" :aria-label="'Target for ' + row.label" style="width: 8rem; text-align: right" @change="saveIncomeTarget(row.source, $event)" /></td>
                    <td data-align="right">{{ formatPrice(row.received) }}</td>
                    <td data-align="right">{{ row.target ? formatPrice(Math.max(row.remaining, 0)) : '—' }}</td>
                  </tr>
                  <tr>
                    <td data-emphasis>Total</td>
                    <td data-align="right" data-emphasis>{{ formatPrice(budget.income_target_total) }}</td>
                    <td data-align="right" data-emphasis>{{ formatPrice(budget.income_received_total) }}</td>
                    <td data-align="right" data-emphasis>{{ budget.income_target_total ? formatPrice(Math.max(budget.income_target_total - budget.income_received_total, 0)) : '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <p v-if="budget.income_target_total || budget.budget_total" class="ds-meta" data-testid="planned-net">
            Planned result for {{ budget.year }}: {{ formatPrice(budget.planned_net) }} ({{ formatPrice(budget.income_target_total) }} to raise, {{ formatPrice(budget.budget_total) }} to spend).
          </p>
        </template>
        <p class="ds-caption">Only the general expenses count here; each event keeps its own costs. Leave a box empty for no budget or target. Copying fills only the boxes that are still empty. Income counts gifts, membership payments and income added by hand.</p>
      </section>

      <section style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <div style="display: flex; justify-content: space-between; align-items: center; gap: var(--ds-space-3); flex-wrap: wrap">
          <h2 class="ds-title">Expenses</h2>
          <BaseButton type="button" variant="secondary" size="sm" class="add-expense" @click="add">Add expense</BaseButton>
        </div>
        <BaseEmptyState v-if="expenses.length === 0" title="No expenses yet" description="Add a cost such as rent or printing to follow what you spend." />
        <div v-else class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table">
              <thead><tr><th>Date</th><th>Description</th><th>Category</th><th>Vendor</th><th data-align="right">Amount</th><th>Receipt</th><th></th></tr></thead>
              <tbody>
                <tr v-for="expense in expenses" :key="expense.id">
                  <td>{{ formatEventDate(expense.date) }}</td>
                  <td data-emphasis>{{ expense.description }}</td>
                  <td><span class="ds-badge ds-badge-neutral">{{ categoryLabel(expense.category) }}</span></td>
                  <td>{{ expense.vendor ?? '—' }}</td>
                  <td data-align="right">{{ formatPrice(expense.amount) }}</td>
                  <td>
                    <BaseButton v-if="expense.receipt_url" type="button" variant="ghost" size="sm" @click="openReceipt(expense.receipt_url)">View</BaseButton>
                    <span v-else>—</span>
                  </td>
                  <td data-align="right">
                    <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-1)">
                      <BaseButton type="button" variant="ghost" size="sm" @click="openDetails(expense)">Details</BaseButton>
                      <BaseButton type="button" variant="ghost" size="sm" class="edit-expense" @click="edit(expense)">Edit</BaseButton>
                      <BaseButton type="button" variant="ghost" size="sm" class="delete-expense" @click="deleteTarget = expense">Delete</BaseButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </template>

    <AccountingExpenseModal v-model="showModal" :event-id="null" :expense="editTarget" @saved="load" />
    <BaseModal :model-value="!!deleteTarget" title="Delete expense" @update:model-value="deleteTarget = null">
      <p class="ds-body">Delete the expense "{{ deleteTarget?.description }}"? This cannot be undone.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="deleteTarget = null">Cancel</BaseButton>
        <BaseButton type="button" variant="danger" class="confirm-delete" @click="confirmDelete">Delete</BaseButton>
      </div>
    </BaseModal>
    <AccountingIncomeModal v-model="showIncomeModal" :income="incomeEdit" @saved="load" />
    <BaseModal :model-value="!!incomeDelete" title="Delete income" @update:model-value="incomeDelete = null">
      <p class="ds-body">Delete the income "{{ incomeDelete?.reference }}"? This cannot be undone.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="incomeDelete = null">Cancel</BaseButton>
        <BaseButton type="button" variant="danger" class="confirm-delete-income" @click="confirmDeleteIncome">Delete</BaseButton>
      </div>
    </BaseModal>
    <AccountingReceiptModal v-model="showReceipt" :url="receiptUrl" />
    <AccountingExpenseViewModal v-model="showView" :expense="viewTarget" @edit="editFromDetails" />
  </div>
</template>
