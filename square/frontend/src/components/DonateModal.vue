<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import BaseInput from './ui/BaseInput.vue'
import BaseModal from './ui/BaseModal.vue'
import BaseRadio from './ui/BaseRadio.vue'
import { ValidationError } from '../services/membershipDriveApi'
import { donate, type DonationMethod } from '../services/eventSupportApi'
import { squareProfile } from '../services/squareConfig'
import { useVippsNumber, useVippsQrImage } from '../composables/useVippsNumber'
import VippsQrPicture from './ui/VippsQrPicture.vue'

const props = defineProps<{
  modelValue: boolean
  slug: string
  eventTitle: string
  methods: DonationMethod[]
}>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const vippsNumber = useVippsNumber()
const vippsQrImage = useVippsQrImage()

const PRESETS = [100, 250, 500, 1000]
const METHOD_LABEL: Record<DonationMethod, string> = {
  vipps_app: 'Pay in the Vipps app',
  stripe: 'Pay by card',
  vipps_qr: 'Pay with Vipps QR',
}

const amount = ref('')
const name = ref('')
const email = ref('')
const method = ref<DonationMethod>('vipps_app')
const errors = ref<Record<string, string>>({})
const formError = ref('')
const submitting = ref(false)
const done = ref(false)

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    amount.value = ''
    name.value = ''
    email.value = ''
    errors.value = {}
    formError.value = ''
    done.value = false
    method.value = props.methods[0] ?? 'vipps_app'
  },
)

const amountOre = computed(() => Math.round(Number(amount.value) * 100))

async function submit() {
  errors.value = {}
  formError.value = ''
  if (!amount.value || !(amountOre.value > 0)) {
    errors.value = { amount: 'Enter an amount.' }
    return
  }
  submitting.value = true
  try {
    const res = await donate(props.slug, {
      name: name.value.trim() || undefined,
      email: email.value.trim() || undefined,
      amount: amountOre.value,
      payment_method: method.value,
    })
    if (res.redirect_url) {
      window.location.href = res.redirect_url
      return
    }
    done.value = true
  } catch (err) {
    if (err instanceof ValidationError) errors.value = err.errors
    else formError.value = err instanceof Error ? err.message : 'Could not complete your donation.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <BaseModal :model-value="modelValue" title="Donate" @update:model-value="emit('update:modelValue', $event)">
    <div v-if="done" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <p class="ds-body">
        Thank you for supporting {{ eventTitle }}! Your donation shows up once we have confirmed the Vipps payment.
      </p>
      <div><BaseButton variant="ghost" @click="emit('update:modelValue', false)">Close</BaseButton></div>
    </div>

    <form v-else style="display: flex; flex-direction: column; gap: var(--ds-space-4)" @submit.prevent="submit">
      <p class="ds-meta">Support {{ eventTitle }}. We cover the payment fees, so all of your gift reaches {{ squareProfile.name }}.</p>

      <div>
        <span class="ds-field-label">Amount ({{ squareProfile.currency }})</span>
        <div style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap; margin-bottom: var(--ds-space-2)">
          <button
            v-for="preset in PRESETS"
            :key="preset"
            type="button"
            class="ds-tag"
            :class="{ 'ds-tag-selected': Number(amount) === preset }"
            :aria-pressed="Number(amount) === preset"
            @click="amount = String(preset)"
          >
            {{ preset }} {{ squareProfile.currency }}
          </button>
        </div>
        <BaseInput v-model="amount" label="Or another amount" type="number" inputmode="decimal" />
        <span v-if="errors.amount" class="ds-field-error-text">{{ errors.amount }}</span>
      </div>

      <div>
        <BaseInput v-model="name" label="Your name (leave blank to stay anonymous)" autocomplete="name" />
        <span v-if="errors.name" class="ds-field-error-text">{{ errors.name }}</span>
      </div>
      <div>
        <BaseInput v-model="email" label="Email (optional)" type="email" autocomplete="email" />
        <span v-if="errors.email" class="ds-field-error-text">{{ errors.email }}</span>
      </div>

      <fieldset style="border: 0; padding: 0; display: flex; flex-direction: column; gap: var(--ds-space-2)">
        <legend class="ds-field-label">How would you like to pay?</legend>
        <BaseRadio
          v-for="m in methods"
          :key="m"
          v-model="method"
          :value="m"
          name="donate-method"
          :label="METHOD_LABEL[m]"
        />
        <span v-if="errors.payment_method" class="ds-field-error-text">{{ errors.payment_method }}</span>
      </fieldset>

      <div v-if="method === 'vipps_qr'" style="display: flex; flex-direction: column; gap: var(--ds-space-2); align-items: center">
        <p class="ds-meta" style="text-align: center">
          Vipps <strong>{{ amount || 'your amount' }} {{ squareProfile.currency }}</strong> <template v-if="vippsNumber">to <strong>{{ vippsNumber }}</strong></template
          ><template v-else>with the QR code below</template>, then tap the
          button. We confirm it by hand.
        </p>
        <VippsQrPicture :src="vippsQrImage" />
      </div>

      <div v-if="formError" class="ds-alert ds-alert-danger"><div>{{ formError }}</div></div>

      <BaseButton type="submit" size="lg" full-width :disabled="submitting">
        {{ submitting ? 'Please wait…' : method === 'vipps_app' ? 'Continue to Vipps' : method === 'stripe' ? 'Continue to the card page' : "I've paid — send my donation" }}
      </BaseButton>
    </form>
  </BaseModal>
</template>
