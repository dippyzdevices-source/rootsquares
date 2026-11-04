<script setup lang="ts">
import VippsQrPicture from '../../components/ui/VippsQrPicture.vue'
import { ref, computed, onMounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import {
  fetchDonationConfig,
  giveDonation,
  confirmDonationPayment,
  DonationValidationError,
  type DonationConfig,
  type DonationMethod,
  type DonationResult,
} from '../../services/donationsApi'
import { formatPrice, withCurrency } from '../../utils/money'
import { vippsAppFee } from '../../services/vippsAppApi'
import { useToast } from '../../composables/useToast'

// The public donate page (Donations module). Everything shown is the square's own setting: the suggested amounts, the intro words and the
// payment methods that are switched on (Settings -> Payments). Nothing is shown for an empty setting.
const toast = useToast()
const config = ref<DonationConfig | null>(null)
const loading = ref(true)
const failed = ref(false)

const chosenAmount = ref<number | null>(null) // minor units, from a suggested amount
const customAmount = ref('')
const form = ref({ name: '', email: '', message: '', anonymous: false })
const method = ref<DonationMethod | null>(null)
const errors = ref<Record<string, string>>({})
const submitting = ref(false)
const done = ref<DonationResult | null>(null)
const reported = ref(false)

const METHOD_LABELS: Record<DonationMethod, string> = { app: 'Vipps app', card: 'Card', qr: 'Vipps QR / number', bank: 'Bank transfer', cash: 'Cash' }

const amount = computed(() => {
  if (customAmount.value.trim() !== '') {
    const value = Number(customAmount.value.replace(',', '.'))
    return Number.isFinite(value) ? Math.round(value * 100) : 0
  }
  return chosenAmount.value ?? 0
})

// Only digits and one decimal separator can be typed (at most two decimals).
function onAmountInput(event: Event) {
  const cleaned = (event.target as HTMLInputElement).value.replace(/[^\d.,]/g, '')
  const match = cleaned.match(/^(\d*)([.,]?)(\d{0,2})/)
  customAmount.value = match ? match[1] + match[2] + match[3] : ''
  ;(event.target as HTMLInputElement).value = customAmount.value
  chosenAmount.value = null
}

const bankRows = computed(() => {
  const b = config.value?.bank
  if (!b) return []
  return [
    { label: 'Account holder', value: b.holder },
    { label: 'Bank', value: b.bank_name },
    { label: 'Account number', value: b.account_number },
    { label: 'IBAN', value: b.iban },
    { label: 'BIC / SWIFT', value: b.bic },
  ].filter((row) => row.value)
})

function pickSuggested(value: number) {
  chosenAmount.value = value
  customAmount.value = ''
}

onMounted(async () => {
  try {
    config.value = await fetchDonationConfig()
    method.value = config.value.methods[0] ?? null
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
})

async function submit() {
  if (!config.value || !method.value) return
  errors.value = {}
  submitting.value = true
  try {
    const result = await giveDonation({
      donor_name: form.value.name,
      donor_email: form.value.email,
      amount: amount.value,
      payment_method: method.value,
      anonymous: form.value.anonymous,
      message: form.value.message || undefined,
    })
    if (result.redirect_url) {
      window.location.href = result.redirect_url // the Vipps app or the card page; the provider sends the donor back to /donate/thanks
      return
    }
    done.value = result
  } catch (e) {
    if (e instanceof DonationValidationError) errors.value = e.errors
    else toast.error(e instanceof Error ? e.message : 'Could not send your gift')
  } finally {
    submitting.value = false
  }
}

async function reportPaid() {
  if (!done.value) return
  try {
    await confirmDonationPayment(done.value.reference, form.value.email)
    reported.value = true
  } catch {
    toast.error('Could not send that. Please try again.')
  }
}
</script>

<template>
  <div class="ds-scope">
    <div class="ds-container" style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-5); padding-top: var(--ds-space-8); padding-bottom: var(--ds-space-8)">
      <BaseLoadingState v-if="loading" label="Loading…" />
      <div v-else-if="failed" class="ds-alert ds-alert-danger"><div>We couldn't load this page. Please try again later.</div></div>

      <template v-else-if="config">
        <div class="ds-heading">
          <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Support us</span>
          <h1 class="ds-display ds-display-s">Donate</h1>
        </div>
        <p v-if="config.intro" class="ds-body" style="white-space: pre-line">{{ config.intro }}</p>

        <div v-if="!config.open" class="ds-alert ds-alert-info donate-closed"><div>Donations are not open right now.</div></div>

        <div v-else-if="done" class="ds-card donate-done" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <h2 class="ds-display ds-display-s">Thank you, {{ done.donor_name }}</h2>
          <p class="ds-body">Your gift of {{ formatPrice(done.amount) }} is registered. Reference: <strong>{{ done.reference }}</strong>.</p>
          <template v-if="method === 'qr'">
            <p v-if="config.vipps_number" class="ds-body">Pay with Vipps to <strong>{{ config.vipps_number }}</strong> and write the reference in the message.</p>
            <p v-else-if="config.vipps_qr_image_url" class="ds-body">Pay with Vipps using the QR code below and write the reference in the message.</p>
            <VippsQrPicture :src="config.vipps_qr_image_url" />
            <p v-if="reported" class="ds-body">Thanks. We will check it and e-mail you a receipt.</p>
            <div v-else><BaseButton type="button" variant="primary" class="donate-reported" @click="reportPaid">I have paid</BaseButton></div>
          </template>
          <template v-else-if="method === 'bank' && config.bank">
            <p class="ds-body">Transfer the amount to this account and write the reference <strong>{{ done.reference }}</strong> in the message:</p>
            <dl class="bank-details" style="display: grid; grid-template-columns: max-content 1fr; gap: var(--ds-space-1) var(--ds-space-4); margin: 0">
              <template v-for="row in bankRows" :key="row.label"><dt class="ds-meta">{{ row.label }}</dt><dd style="margin: 0">{{ row.value }}</dd></template>
            </dl>
            <p v-if="config.bank.note" class="ds-body" style="white-space: pre-line">{{ config.bank.note }}</p>
            <p v-if="reported" class="ds-body">Thanks. We will check it and e-mail you a receipt.</p>
            <div v-else><BaseButton type="button" variant="primary" class="donate-reported" @click="reportPaid">I have paid</BaseButton></div>
          </template>
          <template v-else-if="method === 'cash'">
            <p class="ds-body" style="white-space: pre-line">{{ config.cash_note || 'Give the cash to the association. We will e-mail you a receipt once it is received.' }}</p>
          </template>
          <p v-if="config.thanks" class="ds-body" style="white-space: pre-line">{{ config.thanks }}</p>
        </div>

        <form v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)" @submit.prevent="submit">
          <div v-if="config.amounts.length" style="display: flex; flex-wrap: wrap; gap: var(--ds-space-2)">
            <BaseButton
              v-for="value in config.amounts"
              :key="value"
              type="button"
              size="sm"
              :variant="customAmount === '' && chosenAmount === value ? 'primary' : 'secondary'"
              class="donate-amount"
              @click="pickSuggested(value)"
            >
              {{ formatPrice(value).replace('.00', '') }}
            </BaseButton>
          </div>
          <label class="ds-field">
            <span class="ds-field-label">{{ config.amounts.length ? 'Another amount' : 'Amount' }} ({{ withCurrency('', config.currency).trim() || config.currency }})</span>
            <span class="ds-field-control"><input :value="customAmount" type="text" inputmode="decimal" class="ds-field-input donate-custom" placeholder="0" @input="onAmountInput" /></span>
            <span v-if="errors.amount" class="ds-field-error-text">{{ errors.amount }}</span>
          </label>
          <label class="ds-field">
            <span class="ds-field-label">Your name</span>
            <span class="ds-field-control"><input v-model="form.name" type="text" class="ds-field-input" /></span>
            <span v-if="errors.donor_name" class="ds-field-error-text">{{ errors.donor_name }}</span>
          </label>
          <label class="ds-field">
            <span class="ds-field-label">Email (for your receipt)</span>
            <span class="ds-field-control"><input v-model="form.email" type="email" class="ds-field-input" /></span>
            <span v-if="errors.donor_email" class="ds-field-error-text">{{ errors.donor_email }}</span>
          </label>
          <label class="ds-field">
            <span class="ds-field-label">Message (optional)</span>
            <span class="ds-field-control"><textarea v-model="form.message" rows="3" class="ds-field-input" /></span>
          </label>
          <label style="display: flex; gap: var(--ds-space-2); align-items: center">
            <input v-model="form.anonymous" type="checkbox" />
            <span class="ds-body">Do not show my name to others</span>
          </label>
          <fieldset v-if="config.methods.length > 1" style="border: 0; padding: 0; display: flex; gap: var(--ds-space-4); flex-wrap: wrap">
            <legend class="ds-field-label">How do you want to give?</legend>
            <label v-for="m in config.methods" :key="m" style="display: flex; gap: var(--ds-space-2); align-items: center">
              <input v-model="method" type="radio" :value="m" />
              <span class="ds-body">{{ METHOD_LABELS[m] }}</span>
            </label>
          </fieldset>
          <p v-if="errors.payment_method" class="ds-field-error-text">{{ errors.payment_method }}</p>
          <p v-if="method === 'app' && config.surcharge_percent && amount >= config.min_amount" class="ds-caption">
            The Vipps app adds a {{ config.surcharge_percent }}% fee ({{ formatPrice(vippsAppFee(amount, config.surcharge_percent)) }}); you pay {{ formatPrice(amount + vippsAppFee(amount, config.surcharge_percent)) }}.
          </p>
          <p v-if="method === 'card' && config.card_surcharge_percent && amount >= config.min_amount" class="ds-caption">
            Paying by card adds a {{ config.card_surcharge_percent }}% fee ({{ formatPrice(vippsAppFee(amount, config.card_surcharge_percent)) }}); you pay {{ formatPrice(amount + vippsAppFee(amount, config.card_surcharge_percent)) }}.
          </p>
          <div><BaseButton type="submit" variant="primary" :disabled="submitting" class="donate-submit">{{ submitting ? 'Sending…' : 'Give' }}</BaseButton></div>
        </form>
      </template>
    </div>
  </div>
</template>
