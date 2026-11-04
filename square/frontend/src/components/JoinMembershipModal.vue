<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import BaseInput from './ui/BaseInput.vue'
import BaseModal from './ui/BaseModal.vue'
import BaseRadio from './ui/BaseRadio.vue'
import { ValidationError } from '../services/membershipDriveApi'
import {
  fetchJoinOptions,
  joinMembership,
  type JoinPaymentMethod,
  type JoinResult,
} from '../services/membershipJoinApi'
import type { MembershipTypeOption } from '../services/memberApi'
import { formatMembershipPrice } from '../utils/membership'
import { humanize } from '../utils/formatEnum'
import { useVippsNumber, useVippsQrImage } from '../composables/useVippsNumber'
import VippsQrPicture from './ui/VippsQrPicture.vue'
import { formatPrice } from '../utils/money'
import { vippsAppFee } from '../services/vippsAppApi'

const props = defineProps<{ modelValue: boolean; type: MembershipTypeOption | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const vippsNumber = useVippsNumber()
const vippsQrImage = useVippsQrImage()

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const METHOD_LABEL: Record<JoinPaymentMethod, string> = {
  vipps_app: 'Pay in the Vipps app',
  stripe: 'Pay by card',
  vipps_qr: 'Pay with Vipps QR',
  pay_later: 'Pay later',
}

const name = ref('')
const email = ref('')
const phone = ref('')
const method = ref<JoinPaymentMethod>('pay_later')
const methods = ref<JoinPaymentMethod[]>(['pay_later'])
const feePercent = ref<Partial<Record<JoinPaymentMethod, number>>>({})
const errors = ref<Record<string, string>>({})
const formError = ref('')
const submitting = ref(false)
const result = ref<JoinResult | null>(null)

const isChild = computed(() => props.type?.name.toLowerCase() === 'child')
const hasPrice = computed(() => !!props.type && !props.type.contact_for_price)
const offeredMethods = computed(() => (hasPrice.value ? methods.value : (['pay_later'] as JoinPaymentMethod[])))

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    name.value = ''
    email.value = ''
    phone.value = ''
    errors.value = {}
    formError.value = ''
    result.value = null
    const options = await fetchJoinOptions()
    methods.value = options.payment_methods
    feePercent.value = options.convenience_percent
    method.value = methods.value[0] ?? 'pay_later'
  },
)

// Membership prices are whole kroner; fees and totals are shown in kroner too (computed like the backend).
const baseOre = computed(() => (props.type?.price ?? 0) * 100)
function feeFor(m: JoinPaymentMethod): number {
  return m === 'pay_later' ? 0 : vippsAppFee(baseOre.value, feePercent.value[m] ?? 0)
}
const fee = computed(() => feeFor(method.value))

function validate(): boolean {
  const e: Record<string, string> = {}
  if (!name.value.trim()) e.name = 'This field is required.'
  const mail = email.value.trim()
  if (!mail) e.email = 'This field is required.'
  else if (!EMAIL_RE.test(mail)) e.email = 'Enter a valid email address.'
  errors.value = e
  return Object.keys(e).length === 0
}

async function submit() {
  if (!props.type || !validate()) return
  formError.value = ''
  submitting.value = true
  try {
    const res = await joinMembership({
      membership_type: props.type.name,
      name: name.value.trim(),
      ...(isChild.value ? { parent_email: email.value.trim() } : { email: email.value.trim() }),
      phone: phone.value.trim() || undefined,
      payment_method: hasPrice.value ? method.value : 'pay_later',
    })
    if (res.redirect_url) {
      window.location.href = res.redirect_url
      return
    }
    result.value = res
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = { ...err.errors, email: err.errors.email ?? err.errors.parent_email ?? '' }
      if (err.errors.membership_type || err.errors.payment_method) {
        formError.value = err.errors.membership_type ?? err.errors.payment_method
      }
    } else {
      formError.value = err instanceof Error ? err.message : 'Could not complete your signup.'
    }
  } finally {
    submitting.value = false
  }
}

const submitLabel = computed(() => {
  if (!hasPrice.value) return 'Send my request'
  if (method.value === 'vipps_app') return 'Continue to Vipps'
  if (method.value === 'stripe') return 'Continue to the card page'
  if (method.value === 'vipps_qr') return "I've paid — send my request"
  return 'Join now, pay later'
})
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    :title="type ? `Join as ${humanize(type.name)}` : 'Join'"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="result" class="join-done" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <p class="ds-body">
        <template v-if="result.payment">
          Thank you! We have your {{ humanize(result.membership_type) }} membership request and will activate it as
          soon as we confirm your payment.
        </template>
        <template v-else>
          Thank you! Your {{ humanize(result.membership_type) }} membership request is saved. Log in with
          <strong>{{ email }}</strong> to pay and activate it<template v-if="!hasPrice"> — we will confirm it with you</template>.
        </template>
      </p>
      <div style="display: flex; gap: var(--ds-space-3); flex-wrap: wrap">
        <BaseButton v-if="!result.payment && hasPrice" to="/login">Log in to pay</BaseButton>
        <BaseButton variant="ghost" @click="emit('update:modelValue', false)">Close</BaseButton>
      </div>
    </div>

    <form v-else-if="type" style="display: flex; flex-direction: column; gap: var(--ds-space-4)" @submit.prevent="submit">
      <p class="ds-meta">
        {{ formatMembershipPrice(type) }}
        <template v-if="isChild"> · a parent with an active membership signs up their child.</template>
      </p>

      <div>
        <BaseInput v-model="name" :label="isChild ? 'Child\'s full name' : 'Full name'" autocomplete="name" />
        <span v-if="errors.name" class="ds-field-error-text">{{ errors.name }}</span>
      </div>
      <div>
        <BaseInput
          v-model="email"
          :label="isChild ? 'Parent\'s email (an existing member)' : 'Email'"
          type="email"
          autocomplete="email"
        />
        <span v-if="errors.email" class="ds-field-error-text">{{ errors.email }}</span>
      </div>
      <div>
        <BaseInput v-model="phone" label="Mobile (optional)" type="tel" autocomplete="tel" />
        <span v-if="errors.phone" class="ds-field-error-text">{{ errors.phone }}</span>
      </div>

      <fieldset v-if="hasPrice" style="border: 0; padding: 0; display: flex; flex-direction: column; gap: var(--ds-space-2)">
        <legend class="ds-field-label">How would you like to pay?</legend>
        <BaseRadio
          v-for="m in offeredMethods"
          :key="m"
          v-model="method"
          :value="m"
          name="join-method"
          :label="METHOD_LABEL[m]"
          :description="feeFor(m) > 0 ? `+ ${formatPrice(feeFor(m))} convenience fee` : undefined"
        />
      </fieldset>

      <div v-if="hasPrice && method === 'vipps_qr'" style="display: flex; flex-direction: column; gap: var(--ds-space-2); align-items: center">
        <p class="ds-meta" style="text-align: center">
          Vipps <template v-if="vippsNumber">to <strong>{{ vippsNumber }}</strong></template
          ><template v-else>with the QR code below</template>, mentioning <strong>{{ name.trim() || 'your name' }}</strong>.
          Tap the button once you have paid — an admin confirms it.
        </p>
        <VippsQrPicture :src="vippsQrImage" />
      </div>

      <p v-if="hasPrice && fee > 0" class="ds-body" data-testid="join-total">
        {{ formatPrice(baseOre) }} + {{ formatPrice(fee) }} convenience fee =
        <strong style="color: var(--ds-text-heading)">{{ formatPrice(baseOre + fee) }}</strong>
      </p>

      <div v-if="formError" class="ds-alert ds-alert-danger"><div>{{ formError }}</div></div>

      <BaseButton type="submit" size="lg" full-width :disabled="submitting">{{ submitting ? 'Please wait…' : submitLabel }}</BaseButton>
    </form>
  </BaseModal>
</template>
