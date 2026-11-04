<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import { fetchAdminDonations, exportDonations, adminDonationAction, type AdminDonation } from '../../services/donationsApi'
import { fetchAdminSettings, updateAdminSettings, ValidationError } from '../../services/adminSettingsApi'
import { formatPrice } from '../../utils/money'
import { formatEventDate } from '../../utils/date'
import { downloadBlob } from '../../utils/download'
import { useToast } from '../../composables/useToast'
import { suggestionsFor, groupLabel } from '../../services/starterSuggestions'

const toast = useToast()
const items = ref<AdminDonation[]>([])
const total = ref(0)
const paidTotal = ref(0)
const page = ref(1)
const perPage = 25
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / perPage)))
const loading = ref(true)
const exporting = ref(false)
const search = ref('')
const status = ref('')
const statusOptions = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Waiting for payment' },
  { value: 'pending_verification', label: 'Says paid, to check' },
  { value: 'paid', label: 'Paid' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'cancelled', label: 'Cancelled' },
]
const STATUS_LABEL = Object.fromEntries(statusOptions.map((o) => [o.value, o.label]))
const tone = (s: string) => (s === 'paid' ? 'ds-badge-success' : s === 'rejected' || s === 'cancelled' ? 'ds-badge-neutral' : 'ds-badge-warning')
const METHOD_LABEL: Record<string, string> = { cash: 'Cash', vipps_qr: 'Vipps QR', bank_transfer: 'Bank transfer', vipps_app: 'Vipps app' }

async function load() {
  loading.value = true
  try {
    const result = await fetchAdminDonations({ q: search.value, status: status.value, page: page.value })
    items.value = result.items
    total.value = result.total
    paidTotal.value = result.paid_total
  } catch {
    toast.error('Could not load donations')
  } finally {
    loading.value = false
  }
}
function reload() {
  if (page.value !== 1) page.value = 1
  else void load()
}
watch(status, reload)
watch(page, load)
onMounted(load)

async function act(donation: AdminDonation, action: 'mark-paid' | 'reject') {
  try {
    await adminDonationAction(donation.id, action)
    toast.success(action === 'mark-paid' ? 'Marked as paid. A receipt was sent.' : 'Rejected')
    await load()
  } catch {
    toast.error('Could not update this donation')
  }
}

async function handleExport() {
  exporting.value = true
  try {
    downloadBlob(await exportDonations({ q: search.value, status: status.value }), 'donations.xlsx')
  } catch {
    toast.error('Could not export donations')
  } finally {
    exporting.value = false
  }
}

// The donate page's own words and amounts (the square's settings; an empty value is simply not shown).
const settings = ref({ donation_amounts: '', donation_intro: '', donation_thanks: '' })
const settingsErrors = ref<Record<string, string>>({})
const savingSettings = ref(false)
onMounted(async () => {
  try {
    const s = await fetchAdminSettings()
    settings.value = { donation_amounts: s.donation_amounts ?? '', donation_intro: s.donation_intro ?? '', donation_thanks: s.donation_thanks ?? '' }
  } catch {
    toast.error('Could not load the donate page settings')
  }
})
// Words that fit the kind of group, put into the boxes for the owner to read, change and save (nothing is saved by this).
function useSuggested() {
  const s = suggestionsFor()
  settings.value = { ...settings.value, donation_intro: s.donation_intro, donation_thanks: s.donation_thanks }
}

async function saveSettings() {
  savingSettings.value = true
  settingsErrors.value = {}
  try {
    await updateAdminSettings({ ...settings.value })
    toast.success('Saved')
  } catch (e) {
    if (e instanceof ValidationError) settingsErrors.value = e.errors
    else toast.error('Could not save')
  } finally {
    savingSettings.value = false
  }
}
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">Donations</h1>
        </div>
        <BaseButton size="sm" type="button" variant="secondary" class="export-donations" :disabled="exporting" @click="handleExport">{{ exporting ? 'Exporting…' : 'Export to Excel' }}</BaseButton>
      </div>
      <p class="ds-body">Received so far (paid gifts): <strong>{{ formatPrice(paidTotal) }}</strong>. The donate page is at <a href="/donate">/donate</a>.</p>

      <hr class="ds-section-line" />

      <div class="ds-toolbar">
        <BaseSearchField v-model="search" size="sm" class="ds-toolbar-search" placeholder="Name, email or reference" @keyup.enter="reload" />
        <BaseSelect v-model="status" size="sm" class="ds-toolbar-select-wide" :options="statusOptions" highlight-active />
      </div>

      <BaseLoadingState v-if="loading" label="Loading donations…" />
      <div v-else-if="items.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)"><p class="ds-meta">No donations yet.</p></div>
      <div v-else class="ds-table-wrap">
        <div class="ds-table-scroll">
          <table class="ds-table">
            <thead>
              <tr><th>Gift</th><th>Donor</th><th data-align="right">Amount</th><th>Method</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="d in items" :key="d.id">
                <td data-emphasis>{{ d.reference }}<div class="ds-caption">{{ formatEventDate(d.created_at) }}</div></td>
                <td>
                  {{ d.donor_name }}<span v-if="d.anonymous" class="ds-badge ds-badge-neutral" style="margin-left: var(--ds-space-2)">anonymous</span>
                  <div class="ds-caption">{{ d.donor_email }}</div>
                  <div v-if="d.message" class="ds-caption" style="white-space: pre-line">{{ d.message }}</div>
                </td>
                <td data-align="right">{{ formatPrice(d.amount) }}</td>
                <td>{{ d.payment_method ? (METHOD_LABEL[d.payment_method] ?? d.payment_method) : '—' }}</td>
                <td><span class="ds-badge" :class="tone(d.status)">{{ STATUS_LABEL[d.status] ?? d.status }}</span></td>
                <td data-align="right">
                  <div v-if="d.status === 'pending' || d.status === 'pending_verification'" style="display: flex; gap: var(--ds-space-2); justify-content: flex-end">
                    <BaseButton type="button" size="sm" variant="primary" class="mark-paid" @click="act(d, 'mark-paid')">Mark paid</BaseButton>
                    <BaseButton type="button" size="sm" variant="ghost" class="reject" @click="act(d, 'reject')">Reject</BaseButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <PaginationBar v-model:page="page" :total-pages="totalPages" :total="total" />

      <section class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <h2 class="ds-title">The donate page</h2>
        <label class="ds-field">
          <span class="ds-field-label">Suggested amounts (whole amounts, separated by commas; empty = the donor types an amount)</span>
          <span class="ds-field-control"><input v-model="settings.donation_amounts" type="text" placeholder="100,250,500" class="ds-field-input" /></span>
          <span v-if="settingsErrors.donation_amounts" class="ds-field-error-text">{{ settingsErrors.donation_amounts }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Words above the form (empty = none)</span>
          <span class="ds-field-control"><textarea v-model="settings.donation_intro" rows="3" class="ds-field-input" /></span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Thank-you words, shown after giving and in the receipt e-mail (empty = none)</span>
          <span class="ds-field-control"><textarea v-model="settings.donation_thanks" rows="3" class="ds-field-input" /></span>
        </label>
        <div><BaseButton type="button" variant="ghost" size="sm" class="use-suggested" @click="useSuggested">Fill in suggested words{{ groupLabel() ? ` for a ${groupLabel()}` : '' }}</BaseButton></div>
        <p class="ds-caption">The payment methods are the ones switched on under Settings, Payments. Tax-deduction wording, if your country has it, goes in the thank-you words.</p>
        <div><BaseButton type="button" variant="primary" size="sm" :disabled="savingSettings" @click="saveSettings">{{ savingSettings ? 'Saving…' : 'Save' }}</BaseButton></div>
      </section>
    </div>
  </div>
</template>
