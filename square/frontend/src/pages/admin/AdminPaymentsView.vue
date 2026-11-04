<script setup lang="ts">
import { moduleEnabled } from '../../services/modules'
import { squareProfile } from '../../services/squareConfig'
import { ref, watch, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import BaseAvatar from '../../components/ui/BaseAvatar.vue'
import BaseMultiSelect from '../../components/ui/BaseMultiSelect.vue'
import BaseSearchField from '../../components/ui/BaseSearchField.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import PaginationBar from '../../components/ui/PaginationBar.vue'
import {
  exportPayments,
  fetchAdminPayments,
  refundPayment,
  checkVippsPayment,
  startVippsTestPayment,
  fetchVippsStatus,
  reviewPayment,
  type AdminPaymentItem,
} from '../../services/adminPaymentsApi'
import { downloadBlob } from '../../utils/download'
import { formatPrice } from '../../utils/money'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: providerLabel } = useLookup('payment_provider')
const { label: paymentStatusLabel } = useLookup('payment_status')
const { label: paymentTypeLabel } = useLookup('payment_type')
const toast = useToast()
const router = useRouter() as ReturnType<typeof useRouter> | undefined

// A row opens what the payment belongs to: the order (ticket) or the member (membership). The
// admin test payment has neither, so its row isn't clickable.
function rowTarget(payment: AdminPaymentItem): string | null {
  if (payment.order_id) return `/admin/orders/${payment.order_id}`
  if (payment.member_id) return `/admin/members/${payment.member_id}`
  return null
}

// Tapping anywhere on a row opens it; real links/buttons inside keep their own action.
function openPayment(event: MouseEvent, payment: AdminPaymentItem) {
  if ((event.target as HTMLElement).closest('a, button, label, input')) return
  const target = rowTarget(payment)
  if (target) void router?.push(target)
}
const exporting = ref(false)
const loading = ref(true)
const payments = ref<AdminPaymentItem[]>([])
// ?q=<reference> (from the order page's payment links) pre-fills the search.
const search = ref(new URLSearchParams(window.location.search).get('q') ?? '')
const paymentType = ref<string[]>([])
const status = ref<string[]>([])
const provider = ref<string[]>([])
const page = ref(1)
const totalPages = ref(1)

const paymentTypeOptions = computed(() => [
  ...(moduleEnabled('tickets') ? [{ value: 'event_ticket', label: paymentTypeLabel('event_ticket') }] : []),
  ...(moduleEnabled('memberships') ? [{ value: 'membership', label: paymentTypeLabel('membership') }] : []),
])

const statusOptions = computed(() => [
  { value: 'pending', label: paymentStatusLabel('pending') },
  { value: 'initiated', label: paymentStatusLabel('initiated') },
  { value: 'paid', label: paymentStatusLabel('paid') },
  { value: 'failed', label: paymentStatusLabel('failed') },
  { value: 'cancelled', label: paymentStatusLabel('cancelled') },
  { value: 'refunded', label: paymentStatusLabel('refunded') },
])

const providerOptions = computed(() => [
  { value: 'cash', label: providerLabel('cash') },
  { value: 'vipps_qr', label: providerLabel('vipps_qr') },
  { value: 'bank_transfer', label: providerLabel('bank_transfer') },
  { value: 'vipps_app', label: providerLabel('vipps_app') },
  { value: 'stripe', label: providerLabel('stripe') },
])

function statusTone(value: string): string {
  if (value === 'paid') return 'ds-badge-success'
  if (value === 'failed' || value === 'cancelled') return 'ds-badge-danger'
  if (value === 'refunded') return 'ds-badge-info'
  return 'ds-badge-neutral'
}

async function load() {
  loading.value = true
  try {
    const data = await fetchAdminPayments({
      page: page.value,
      q: search.value || undefined,
      payment_type: paymentType.value,
      status: status.value,
      provider: provider.value,
    })
    payments.value = data.items
    totalPages.value = data.total_pages
  } catch {
    toast.error('Could not load payments')
  } finally {
    loading.value = false
  }
}

watch([paymentType, status, provider], () => {
  page.value = 1
  load()
})
watch(page, load)

function onSearch() {
  page.value = 1
  load()
}

// Refund confirmation. Vipps App: one confirmation (we send the money back ourselves).
// Manual: two — the association must have returned the money by hand BEFORE marking it refunded.
const refundTarget = ref<AdminPaymentItem | null>(null)
const refundStep = ref<1 | 2>(1)
const moneyReturned = ref(false)
const refunding = ref(false)

function startRefund(payment: AdminPaymentItem) {
  refundTarget.value = payment
  refundStep.value = 1
  moneyReturned.value = false
}

function closeRefund() {
  if (!refunding.value) refundTarget.value = null
}

async function confirmRefund() {
  const payment = refundTarget.value
  if (!payment) return
  refunding.value = true
  try {
    await refundPayment(payment.id, 'Refunded by admin')
    toast.success(
      payment.refund_mode === 'vipps'
        ? "Refund sent via Vipps — it can take a few days to appear on the customer's statement."
        : 'Payment marked as refunded',
      7000,
    )
    refundTarget.value = null
    await load()
  } catch (err) {
    toast.error(err instanceof Error && err.message ? err.message : 'Could not refund this payment')
  } finally {
    refunding.value = false
  }
}

const startingTest = ref(false)
// The test button exists only while Vipps is configured but not yet live for customers.
const showVippsTest = ref(false)
void fetchVippsStatus().then((s) => (showVippsTest.value = s.configured && !s.public))

async function handleVippsTest() {
  startingTest.value = true
  try {
    const { redirect_url } = await startVippsTestPayment()
    window.location.href = redirect_url
  } catch {
    toast.error('Could not start the Vipps test payment')
    startingTest.value = false
  }
}

async function handleVippsCheck(payment: AdminPaymentItem) {
  try {
    const updated = await checkVippsPayment(payment.id)
    if (updated.status === 'paid') toast.success('Payment confirmed by Vipps')
    else if (updated.status === 'initiated') toast.info('Vipps has not confirmed this payment yet')
    else toast.info(`Payment is ${paymentStatusLabel(updated.status)}`)
    await load()
  } catch {
    toast.error('Could not check this payment with Vipps')
  }
}

async function handleReview(payment: AdminPaymentItem, action: 'confirm' | 'reject') {
  try {
    await reviewPayment(payment.id, action)
    toast.success(action === 'confirm' ? 'Payment confirmed' : 'Payment rejected')
    await load()
  } catch {
    toast.error('Could not update this payment')
  }
}

async function handleExport() {
  exporting.value = true
  try {
    const blob = await exportPayments({
      q: search.value || undefined,
      payment_type: paymentType.value,
      status: status.value,
      provider: provider.value,
    })
    downloadBlob(blob, 'payments.xlsx')
  } catch {
    toast.error('Could not export payments')
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope">
    <div style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
          <h1 class="ds-display ds-display-s">Payments</h1>
        </div>
          <BaseButton size="sm" type="button" variant="secondary" class="export-payments" :disabled="exporting" @click="handleExport">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
          {{ exporting ? 'Exporting…' : 'Export to Excel' }}
        </BaseButton>
      </div>

      <hr class="ds-section-line" />

      <div class="ds-toolbar">
        <BaseSearchField size="sm" class="ds-toolbar-search" v-model="search" placeholder="Reference, payer name, or email" @keyup.enter="onSearch" />
        <BaseMultiSelect size="sm" class="ds-toolbar-select" v-model="paymentType" :options="paymentTypeOptions" all-label="All types" aria-label="Filter by type" highlight-active />
        <BaseMultiSelect size="sm" class="ds-toolbar-select" v-model="status" :options="statusOptions" all-label="All statuses" aria-label="Filter by status" highlight-active />
        <BaseMultiSelect size="sm" class="ds-toolbar-select" v-model="provider" :options="providerOptions" all-label="All providers" aria-label="Filter by provider" highlight-active />
          <BaseButton size="sm" v-if="showVippsTest" type="button" variant="secondary" class="vipps-test-payment" :disabled="startingTest" :title="`A real 1 ${squareProfile.currency} payment (plus fee) through Vipps App, to test it end to end`" @click="handleVippsTest">
            {{ startingTest ? 'Opening Vipps…' : `Vipps test payment (1 ${squareProfile.currency})` }}
          </BaseButton>
      </div>

      <BaseLoadingState v-if="loading" label="Loading payments…" />
      <div v-else-if="payments.length === 0" class="ds-card ds-card-sunken" style="text-align: center; padding: var(--ds-space-8)">
        <p class="ds-meta">No payments found.</p>
      </div>
      <template v-else>
        <div class="ds-table-wrap">
          <div class="ds-table-scroll">
            <table class="ds-table" style="min-width: 700px; table-layout: fixed">
              <colgroup>
                <col style="width: 200px" />
                <col style="width: 180px" />
                <col style="width: 110px" />
                <col style="width: 110px" />
                <col style="width: 110px" />
              </colgroup>
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Paid by</th>
                  <th data-align="right">Amount</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="payment in payments"
                  :key="payment.id"
                  :class="{ 'ds-row-clickable': rowTarget(payment) }"
                  @click="openPayment($event, payment)"
                >
                  <td data-emphasis>
                    <span style="display: inline-flex; align-items: center; gap: var(--ds-space-2); white-space: nowrap; font-variant-numeric: tabular-nums">
                      <svg v-if="payment.payment_type === 'membership'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0; opacity: 0.6"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
                      <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0; opacity: 0.6"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>
                      {{ payment.payment_reference ?? '—' }}
                    </span>
                    <div class="ds-caption">
                      {{ paymentTypeLabel(payment.payment_type) }}
                      <template v-if="payment.order_id && payment.order_number">
                        · <router-link :to="`/admin/orders/${payment.order_id}`" class="order-link" style="font-weight: 600">{{ payment.order_number }}</router-link>
                      </template>
                    </div>
                  </td>
                  <td style="overflow: hidden">
                    <span style="display: inline-flex; align-items: center; gap: var(--ds-space-2); min-width: 0; max-width: 100%">
                      <BaseAvatar :name="payment.payer_name" size="sm" />
                      <span style="min-width: 0; overflow: hidden">
                        <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="payment.payer_name ?? undefined">
                          <router-link v-if="payment.member_id" :to="`/admin/members/${payment.member_id}`" class="member-link" style="font-weight: 600">{{ payment.payer_name ?? '—' }}</router-link>
                          <template v-else>{{ payment.payer_name ?? '—' }}</template>
                        </div>
                        <div v-if="payment.payer_email" class="ds-caption" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="payment.payer_email">{{ payment.payer_email }}</div>
                      </span>
                    </span>
                  </td>
                  <td data-align="right" style="white-space: nowrap">{{ formatPrice(payment.amount) }}</td>
                  <td style="white-space: nowrap">
                    <span class="ds-badge" :class="statusTone(payment.status)">{{ paymentStatusLabel(payment.status) }}</span>
                    <div class="ds-caption payment-provider">{{ providerLabel(payment.provider) }}</div>
                  </td>
                  <td data-align="right">
                    <div style="display: flex; justify-content: flex-end; flex-wrap: wrap; gap: var(--ds-space-2)">
                    <template v-if="payment.status === 'pending' && payment.payment_type === 'membership'">
                      <BaseIconButton variant="success" size="sm" class="confirm-payment" :label="`Confirm ${payment.payment_reference ?? 'payment'}`" @click="handleReview(payment, 'confirm')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
                      </BaseIconButton>
                      <BaseIconButton variant="danger" size="sm" class="reject-payment" :label="`Reject ${payment.payment_reference ?? 'payment'}`" @click="handleReview(payment, 'reject')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>
                      </BaseIconButton>
                    </template>
                    <BaseIconButton variant="bare"
                      v-if="payment.status === 'initiated' && (payment.provider === 'vipps_app' || payment.provider === 'stripe')"
                      size="sm"
                      class="check-vipps"
                      :label="`Check ${payment.payment_reference ?? 'payment'} with the payment provider`"
                      @click="handleVippsCheck(payment)"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" /></svg>
                    </BaseIconButton>
                    <BaseIconButton variant="warning"
                      v-if="payment.status === 'paid'"
                      size="sm"
                      class="refund-payment"
                      :label="`Refund ${payment.payment_reference ?? 'payment'}`"
                      :disabled="!!payment.refund_blocked_reason"
                      :title="payment.refund_blocked_reason ?? undefined"
                      @click="startRefund(payment)"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 14 4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11" /></svg>
                    </BaseIconButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <PaginationBar v-model:page="page" :total-pages="totalPages" />
      </template>

    <BaseModal
      :model-value="refundTarget !== null"
      :title="refundTarget?.refund_mode === 'vipps' ? 'Refund via Vipps' : 'Refund — manual payment'"
      @update:model-value="(open) => { if (!open) closeRefund() }"
    >
      <div v-if="refundTarget" class="refund-modal" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-body">
          <strong>{{ refundTarget.payment_reference }}</strong> · {{ formatPrice(refundTarget.amount) }}
          <template v-if="refundTarget.payer_name"> · {{ refundTarget.payer_name }}</template>
        </p>

        <template v-if="refundTarget.refund_mode === 'vipps'">
          <div class="ds-alert ds-alert-info">
            <div>
              {{ formatPrice(refundTarget.amount) }}<template v-if="refundTarget.surcharge_amount"> (including the {{ formatPrice(refundTarget.surcharge_amount) }} convenience fee)</template>
              will be sent back to the customer through Vipps right now. This can't be undone.
              Card refunds can take a few business days to appear on the customer's statement.
            </div>
          </div>
        </template>

        <template v-else-if="refundStep === 1">
          <div class="ds-alert ds-alert-danger">
            <div>
              <strong>This was not paid through Vipps-App, so nothing is sent back automatically.</strong>
              You must return {{ formatPrice(refundTarget.amount) }} to the customer yourself (cash, Vipps or bank transfer)
              <em>before</em> marking it as refunded here.
            </div>
          </div>
        </template>
        <template v-else>
          <div class="ds-alert ds-alert-danger">
            <div><strong>Second check.</strong> Marking it refunded only updates our records; the customer gets no money from this.</div>
          </div>
          <label class="ds-checkbox" style="align-items: center">
            <input v-model="moneyReturned" type="checkbox" class="money-returned" />
            <span class="ds-checkbox-box">✓</span>
            <span class="ds-meta">I have already returned {{ formatPrice(refundTarget.amount) }} to {{ refundTarget.payer_name ?? 'the customer' }}.</span>
          </label>
        </template>

        <p class="ds-meta">
          <template v-if="refundTarget.payment_type === 'event_ticket'">The order will be cancelled and its tickets voided, so they stop working at the door.</template>
          <template v-else>The paid periods will become unpaid again; the membership itself stays as it is.</template>
        </p>

        <div style="display: flex; gap: var(--ds-space-3); flex-wrap: wrap; justify-content: center">
          <BaseButton type="button" variant="ghost" :disabled="refunding" @click="closeRefund">Cancel</BaseButton>
          <BaseButton
            v-if="refundTarget.refund_mode !== 'vipps' && refundStep === 1"
            type="button"
            variant="warning"
            class="refund-continue"
            @click="refundStep = 2"
          >
            Continue
          </BaseButton>
          <BaseButton
            v-else
            type="button"
            variant="warning"
            class="refund-confirm"
            :disabled="refunding || (refundTarget.refund_mode !== 'vipps' && !moneyReturned)"
            @click="confirmRefund"
          >
            {{ refunding ? 'Refunding…' : refundTarget.refund_mode === 'vipps' ? `Refund ${formatPrice(refundTarget.amount)} via Vipps` : 'Mark as refunded' }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
    </div>
  </div>
</template>
