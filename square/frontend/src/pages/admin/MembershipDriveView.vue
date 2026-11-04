<script setup lang="ts">
import VippsQrPicture from '../../components/ui/VippsQrPicture.vue'
import { isBlankPhone, isValidPhone, phoneMessage, phonePrefix } from '../../utils/phone'
import { computed, onMounted, ref } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchMembershipTypes, type MembershipTypeOption } from '../../services/memberApi'
import {
  signupMembershipDrive,
  ValidationError,
  type MembershipDriveSignupResult,
  fetchDriveOptions,
} from '../../services/membershipDriveApi'
import { formatMembershipPrice, frequencyLabel } from '../../utils/membership'
import { formatPriceRounded } from '../../utils/money'
import { humanize } from '../../utils/formatEnum'
import { fetchSettings } from '../../services/settingsApi'

// 'pay' is skipped entirely for a contact_for_price type (Lifetime) — there's nothing to
// collect via Vipps, so 'details' submits straight through to the signup call.
type Step = 'select' | 'details' | 'pay' | 'done'


const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const step = ref<Step>('select')
const loading = ref(true)
const loadError = ref(false)
const membershipTypes = ref<MembershipTypeOption[]>([])
const selectedType = ref<MembershipTypeOption | null>(null)

const form = ref({ name: '', email: '', phone: phonePrefix() })
const cashEnabled = ref(false)
const vippsNumber = ref<string | null>(null) // the square's own Vipps number; Vipps QR is offered only while it is set (W6-R38)
const payMethod = ref<'vipps_qr' | 'cash'>('vipps_qr')
const vippsQrImage = ref<string | null>(null)
const vippsAvailable = computed(() => !!vippsNumber.value || !!vippsQrImage.value)
const showCash = computed(() => cashEnabled.value && (!vippsAvailable.value || payMethod.value === 'cash'))
const payLater = ref(false)
const errors = ref<Record<string, string>>({})
const submitting = ref(false)
const submitError = ref('')
const result = ref<MembershipDriveSignupResult | null>(null)

onMounted(load)

async function load() {
  loading.value = true
  loadError.value = false
  try {
    membershipTypes.value = await fetchMembershipTypes()
    // Cash is offered only while an admin has switched it on; failing to ask just leaves it off.
    void fetchDriveOptions()
      .then((options) => {
        cashEnabled.value = options.cash_enabled
        if (!vippsNumber.value && options.cash_enabled) payMethod.value = 'cash'
      })
      .catch(() => (cashEnabled.value = false))
    void fetchSettings()
      .then((settings) => {
        vippsNumber.value = settings.vipps_number ?? null
        vippsQrImage.value = settings.vipps_qr_image_url ?? null
        if (!vippsAvailable.value && cashEnabled.value) payMethod.value = 'cash'
      })
      .catch(() => (vippsNumber.value = null))
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function selectType(type: MembershipTypeOption) {
  selectedType.value = type
  step.value = 'details'
}

// A child has no email/login — the parent's email links them.
const isChild = computed(() => selectedType.value?.name.toLowerCase() === 'child')

function backToSelect() {
  step.value = 'select'
  errors.value = {}
  submitError.value = ''
}

function validate(): boolean {
  const next: Record<string, string> = {}
  if (!form.value.name.trim()) next.name = 'This field is required.'
  const emailKey = isChild.value ? 'parent_email' : 'email'
  if (!form.value.email.trim()) next[emailKey] = 'This field is required.'
  else if (!EMAIL_RE.test(form.value.email.trim())) next[emailKey] = 'Enter a valid email address.'
  const phoneBlank = isBlankPhone(form.value.phone)
  // Phone is optional at the drive; when given it must still be valid for the square's country.
  if (!phoneBlank && !isValidPhone(form.value.phone)) next.phone = phoneMessage()
  errors.value = next
  return Object.keys(next).length === 0
}

function continueFromDetails() {
  if (!selectedType.value) return
  submitError.value = ''
  if (!validate()) return

  // A contact_for_price type has no amount to collect via Vipps — nothing to show a QR for,
  // so it goes straight to activating the membership, same as before this change.
  if (selectedType.value.contact_for_price) {
    void submitSignup()
  } else {
    step.value = 'pay'
  }
}

function backToDetails() {
  step.value = 'details'
  submitError.value = ''
}

async function submitSignup(later = false) {
  if (!selectedType.value || submitting.value) return
  payLater.value = later && !selectedType.value.contact_for_price
  submitError.value = ''

  submitting.value = true
  try {
    result.value = await signupMembershipDrive({
      name: form.value.name.trim(),
      ...(isChild.value
        ? { parent_email: form.value.email.trim() }
        : { email: form.value.email.trim() }),
      phone: isBlankPhone(form.value.phone) ? '' : form.value.phone.trim(),
      membership_type: selectedType.value.name,
      payment_method: selectedType.value.contact_for_price ? undefined : later ? 'pay_later' : payMethod.value,
    })
    step.value = 'done'
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
      step.value = 'details'
    } else {
      submitError.value = 'Something went wrong — please try again.'
    }
  } finally {
    submitting.value = false
  }
}

function startOver() {
  selectedType.value = null
  form.value = { name: '', email: '', phone: phonePrefix() }
  errors.value = {}
  submitError.value = ''
  result.value = null
  payLater.value = false
  step.value = 'select'
}
</script>

<template>
  <div class="ds-container drive-view" style="max-width: 640px; padding-top: var(--ds-space-8); padding-bottom: var(--ds-space-8)">
    <BaseLoadingState v-if="loading" label="Loading membership types…" />

    <div v-else-if="loadError" class="ds-alert ds-alert-danger">
      Couldn't load membership types. <button type="button" class="ds-utility-link" style="color: inherit; opacity: 1; text-decoration: underline" @click="load">Try again</button>.
    </div>

    <template v-else>
      <div v-if="step === 'select'">
        <h1 class="ds-title" style="margin-bottom: var(--ds-space-2)">Choose a membership type</h1>
        <p class="ds-body" style="color: var(--ds-text-muted); margin-bottom: var(--ds-space-6)">
          Tap the type the person wants — you'll enter their details next.
        </p>

        <div v-if="membershipTypes.length === 0" class="ds-alert ds-alert-warning">
          No active membership types are available right now.
        </div>
        <div v-else style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
          <button
            v-for="type in membershipTypes"
            :key="type.name"
            type="button"
            class="ds-card"
            style="display: flex; flex-direction: column; gap: var(--ds-space-1); text-align: left; cursor: pointer; width: 100%"
            @click="selectType(type)"
          >
            <span style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4)">
              <span style="font-weight: 600; color: var(--ds-text-heading)">{{ humanize(type.name) }}</span>
              <span style="color: var(--ds-text-primary); font-weight: 600; white-space: nowrap">{{ formatMembershipPrice(type) }}</span>
            </span>
            <span v-if="type.description" class="ds-meta" style="color: var(--ds-text-muted)">
              {{ type.description }}
            </span>
          </button>
        </div>
      </div>

      <div v-else-if="step === 'details' && selectedType">
        <button type="button" class="ds-utility-link" style="color: var(--ds-text-muted); opacity: 1; margin-bottom: var(--ds-space-4)" @click="backToSelect">&larr; Choose a different type</button>

        <h1 class="ds-title" style="margin-bottom: var(--ds-space-1)">{{ humanize(selectedType.name) }}</h1>
        <p class="ds-body" style="color: var(--ds-text-muted); margin-bottom: var(--ds-space-6)">
          <template v-if="selectedType.contact_for_price">
            No payment is recorded here — the membership activates immediately regardless.
          </template>
          <template v-else>
            Next you'll show them the Vipps-QR to pay <strong style="color: var(--ds-text-heading)">{{ formatMembershipPrice(selectedType) }}</strong>
            for this {{ frequencyLabel(selectedType.billing_frequency) }} — the membership only activates once you confirm the payment.
          </template>
        </p>

        <form style="display: flex; flex-direction: column; gap: var(--ds-space-4)" @submit.prevent="continueFromDetails">
          <label class="ds-field">
            <span class="ds-field-label">Full name</span>
            <span class="ds-field-control" :class="{ 'ds-field-control-error': errors.name }">
              <input v-model="form.name" type="text" placeholder="Full name" class="ds-field-input" />
            </span>
            <span v-if="errors.name" class="ds-field-error-text">{{ errors.name }}</span>
          </label>
          <label class="ds-field">
            <span class="ds-field-label">{{ isChild ? "Parent's email" : 'Email' }}</span>
            <span class="ds-field-control" :class="{ 'ds-field-control-error': errors.email || errors.parent_email }">
              <input v-model="form.email" type="email" :placeholder="isChild ? 'Parent email address' : 'Email address'" class="ds-field-input" />
            </span>
            <span v-if="errors.email || errors.parent_email" class="ds-field-error-text">{{ errors.email || errors.parent_email }}</span>
          </label>
          <label class="ds-field">
            <span class="ds-field-label">Phone (optional)</span>
            <span class="ds-field-control" :class="{ 'ds-field-control-error': errors.phone }">
              <input v-model="form.phone" type="text" placeholder="Phone" class="ds-field-input" />
            </span>
            <span v-if="errors.phone" class="ds-field-error-text">{{ errors.phone }}</span>
          </label>

          <div v-if="submitError" class="ds-alert ds-alert-danger">{{ submitError }}</div>

          <BaseButton type="submit" size="lg" full-width :disabled="submitting">
            {{ submitting ? 'Activating…' : selectedType.contact_for_price ? 'Activate membership' : 'Continue to payment' }}
          </BaseButton>
        </form>
      </div>

      <div v-else-if="step === 'pay' && selectedType">
        <button type="button" class="ds-utility-link" style="color: var(--ds-text-muted); opacity: 1; margin-bottom: var(--ds-space-4)" @click="backToDetails">&larr; Back to details</button>

        <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <div v-if="cashEnabled && vippsAvailable" class="drive-methods" role="radiogroup" aria-label="Payment method" style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
            <label class="ds-tag" :class="{ 'ds-tag-selected': payMethod === 'vipps_qr' }" style="cursor: pointer">
              <input v-model="payMethod" type="radio" name="drive-pay" value="vipps_qr" style="position: absolute; opacity: 0; pointer-events: none" />
              Vipps-QR
            </label>
            <label class="ds-tag" :class="{ 'ds-tag-selected': payMethod === 'cash' }" style="cursor: pointer">
              <input v-model="payMethod" type="radio" name="drive-pay" value="cash" style="position: absolute; opacity: 0; pointer-events: none" />
              Cash
            </label>
          </div>

          <template v-if="vippsAvailable && payMethod === 'vipps_qr'">
            <h2 class="ds-subtitle">Pay with Vipps</h2>
            <p v-if="vippsNumber" class="ds-body" style="text-align: center">
              Vipps to <strong>{{ vippsNumber }}</strong>
            </p>
            <div style="display: flex; justify-content: center"><VippsQrPicture :src="vippsQrImage" /></div>
            <p class="ds-meta">
              Have them pay with the Vipps App
              <strong style="color: var(--ds-text-heading)">{{ formatMembershipPrice(selectedType) }}</strong>
              for this {{ frequencyLabel(selectedType.billing_frequency) }}, mentioning
              <strong>{{ form.name.trim() }}</strong> in the payment message. Only tap "Mark as
              paid" once you've seen the payment come in.
            </p>
          </template>
          <p v-else-if="!showCash" class="ds-meta">No payment method is set up yet. Switch one on under Settings, then Payments.</p>
          <template v-else>
            <h2 class="ds-subtitle">Pay with cash</h2>
            <p class="ds-meta drive-cash">
              Collect <strong style="color: var(--ds-text-heading)">{{ formatMembershipPrice(selectedType) }}</strong>
              in cash for this {{ frequencyLabel(selectedType.billing_frequency) }}. Only tap "Mark as paid" once you
              have the money in hand.
            </p>
          </template>

          <div v-if="submitError" class="ds-alert ds-alert-danger">{{ submitError }}</div>

          <BaseButton type="button" size="lg" full-width :disabled="submitting" @click="submitSignup(false)">
            {{ submitting && !payLater ? 'Marking as paid…' : payMethod === 'cash' && cashEnabled ? "Cash received — mark as paid" : "Payment received — mark as paid" }}
          </BaseButton>
          <BaseButton type="button" variant="ghost" size="lg" full-width class="pay-later" :disabled="submitting" @click="submitSignup(true)">
            {{ submitting && payLater ? 'Saving…' : 'Pay later' }}
          </BaseButton>
          <p class="ds-meta" style="margin: 0">
            "Pay later" saves the signup as a request awaiting payment. It becomes active once they pay (from their dashboard — for a child, their parent's — or an admin confirms it).
          </p>
        </div>
      </div>

      <div v-else-if="step === 'done' && result">
        <div v-if="result.membership.status === 'pending'" class="ds-alert ds-alert-info pay-later-done" style="margin-bottom: var(--ds-space-6)">
          {{ result.member.name }}'s {{ humanize(result.membership.membership_type) }} membership is saved and awaiting payment — it becomes active once they pay.
        </div>
        <div v-else class="ds-alert ds-alert-success" style="margin-bottom: var(--ds-space-6)">
          {{ result.member.name }}'s {{ humanize(result.membership.membership_type) }} membership is now active.
        </div>

        <div class="ds-deflist" style="grid-template-columns: 1fr">
          <div class="ds-deflist-row" style="padding: 0 0 var(--ds-space-3)">
            <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-1)">Name</p>
            <p class="ds-body">{{ result.member.name }}</p>
          </div>
          <div v-if="result.member.email" class="ds-deflist-row" style="padding: var(--ds-space-3) 0">
            <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-1)">Email</p>
            <p class="ds-body">{{ result.member.email }}</p>
          </div>
          <div class="ds-deflist-row" style="padding: var(--ds-space-3) 0">
            <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-1)">Membership</p>
            <p class="ds-body">{{ humanize(result.membership.membership_type) }}</p>
          </div>
          <div class="ds-deflist-row" style="padding: var(--ds-space-3) 0 0; border-bottom: none">
            <p class="ds-eyebrow" style="margin-bottom: var(--ds-space-1)">Collected</p>
            <p class="ds-body">{{ result.payment ? formatPriceRounded(result.payment.amount) : result.membership.status === 'pending' ? 'Not yet — awaiting payment' : 'None (contact pricing)' }}</p>
          </div>
        </div>

        <p v-if="result.member.email" class="ds-body" style="color: var(--ds-text-muted); margin: var(--ds-space-4) 0 var(--ds-space-6)">
          If they later log in with {{ result.member.email }}, they'll see this membership on their dashboard{{ result.membership.status === 'pending' ? ' and can pay it there' : '' }}.
        </p>

        <p v-if="!result.member.email && result.membership.status === 'pending'" class="ds-body pay-later-parent" style="color: var(--ds-text-muted); margin: var(--ds-space-4) 0 var(--ds-space-6)">
          Their parent can pay it from their own member dashboard, and will get a reminder email if it stays unpaid.
        </p>

        <BaseButton size="lg" full-width @click="startOver">Sign up another member</BaseButton>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* Phone layouts: the design system's buttons never wrap (white-space: nowrap), so a long label such as
   "Payment received — mark as paid" spilled out of the card. Let the labels wrap and centre. */
.drive-view :deep(.ds-btn) { white-space: normal; text-align: center; line-height: 1.25; max-width: 100%; height: auto; min-height: 48px; padding-left: 20px; padding-right: 20px; }
</style>
