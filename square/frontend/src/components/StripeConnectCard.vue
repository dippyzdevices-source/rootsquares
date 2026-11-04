<script setup lang="ts">
import { onMounted, ref } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import BaseModal from './ui/BaseModal.vue'
import {
  connectStripe,
  disconnectStripe,
  fetchProviders,
  ProviderKeysError,
  type ProviderStatus,
} from '../services/adminPaymentProvidersApi'
import { useToast } from '../composables/useToast'

const emit = defineEmits<{ changed: [connected: boolean] }>()
const toast = useToast()

const status = ref<ProviderStatus>({ provider: 'stripe', connected: false })
const canEdit = ref(false)
const loading = ref(true)
const open = ref(false)
const confirmReplace = ref(false)
const confirmDisconnect = ref(false)
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const secretKey = ref('')
const webhookSecret = ref('')
const taxCode = ref('')
const managedPayments = ref(false)

async function load() {
  try {
    const view = await fetchProviders()
    status.value = view.providers.stripe ?? { provider: 'stripe', connected: false }
    canEdit.value = view.can_edit
  } catch {
    status.value = { provider: 'stripe', connected: false }
  } finally {
    loading.value = false
    emit('changed', status.value.connected)
  }
}

function openDialog() {
  secretKey.value = '' // the key is never shown again: replacing it means typing it again
  webhookSecret.value = ''
  taxCode.value = ''
  managedPayments.value = false
  errors.value = {}
  open.value = true
}

function closeDialog() {
  open.value = false
  secretKey.value = '' // do not keep the secret in memory longer than needed
  webhookSecret.value = ''
}

async function submit() {
  saving.value = true
  errors.value = {}
  try {
    const view = await connectStripe(secretKey.value, { webhookSecret: webhookSecret.value, managedPayments: managedPayments.value, taxCode: taxCode.value })
    status.value = view.providers.stripe
    canEdit.value = view.can_edit
    closeDialog()
    toast.success('Stripe is connected')
    emit('changed', status.value.connected)
  } catch (e) {
    errors.value = e instanceof ProviderKeysError ? e.errors : { _: 'Could not reach the server. Please try again.' }
  } finally {
    saving.value = false
  }
}

function startReplace() {
  confirmReplace.value = false
  openDialog()
}

async function doDisconnect() {
  confirmDisconnect.value = false
  try {
    const view = await disconnectStripe()
    status.value = view.providers.stripe
    toast.success('Stripe is disconnected')
    emit('changed', status.value.connected)
  } catch (e) {
    toast.error(e instanceof ProviderKeysError ? e.message : 'Could not disconnect Stripe')
  }
}

onMounted(load)
</script>

<template>
  <section class="ds-card stripe-connect" data-testid="stripe-connect" style="padding: var(--ds-space-4) var(--ds-space-5)">
    <div style="display: flex; gap: var(--ds-space-3); align-items: center; flex-wrap: wrap; justify-content: space-between">
      <div style="min-width: 0">
        <strong>Your Stripe account</strong>
        <p class="ds-meta" style="margin: 2px 0 0">
          <template v-if="loading">Checking…</template>
          <template v-else-if="status.connected">
            Connected in {{ status.mode === 'production' ? 'live' : 'test' }} mode<template v-if="status.hint?.key_last4"> · key ending {{ status.hint.key_last4 }}</template
            ><template v-if="status.hint?.restricted"> · restricted key</template>
          </template>
          <template v-else>Not connected. Customers cannot pay by card until you connect your own Stripe account.</template>
        </p>
        <p v-if="status.connected && !status.webhook_registered" class="ds-meta" style="margin: 2px 0 0">
          Payments are confirmed when the customer returns to the site and by a regular check.
        </p>
      </div>
      <div v-if="!loading && canEdit && !status.connected" style="display: flex; gap: var(--ds-space-2)">
        <BaseButton type="button" size="sm" class="stripe-open" @click="openDialog">Connect Stripe</BaseButton>
      </div>
      <p v-else-if="!loading && !canEdit" class="ds-meta" style="margin: 0">Only the owner of the site can change this.</p>
    </div>

    <div
      v-if="!loading && canEdit && status.connected"
      class="danger-zone"
      data-testid="danger-zone"
      style="margin-top: var(--ds-space-4); padding: var(--ds-space-3) var(--ds-space-4); border: 1px solid var(--ds-danger, #b3261e); border-radius: var(--ds-radius-md, 8px)"
    >
      <strong style="color: var(--ds-danger, #b3261e)">Danger zone</strong>
      <div style="display: flex; gap: var(--ds-space-3); align-items: center; justify-content: space-between; flex-wrap: wrap; margin-top: var(--ds-space-2)">
        <span class="ds-meta">Replace the keys with new ones, or disconnect Stripe so customers can no longer pay with it.</span>
        <div style="display: flex; gap: var(--ds-space-2)">
          <BaseButton type="button" size="sm" variant="secondary" class="stripe-open" @click="confirmReplace = true">Replace key</BaseButton>
          <BaseButton type="button" size="sm" variant="danger" class="stripe-disconnect" @click="confirmDisconnect = true">Disconnect</BaseButton>
        </div>
      </div>
    </div>

    <BaseModal v-model="confirmReplace" title="Replace key?">
      <p class="ds-body">The current keys stop working as soon as you save new ones. Only continue if you have the new keys ready.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="confirmReplace = false">Cancel</BaseButton>
        <BaseButton type="button" variant="danger" class="confirm-replace" @click="startReplace">Continue</BaseButton>
      </div>
    </BaseModal>
    <BaseModal v-model="confirmDisconnect" title="Disconnect Stripe?">
      <p class="ds-body">Paying by card stops working on this site right away and the stored keys are deleted. Past payments and orders stay. To use Stripe again you must enter the keys again.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="confirmDisconnect = false">Cancel</BaseButton>
        <BaseButton type="button" variant="danger" class="confirm-disconnect" @click="doDisconnect">Disconnect</BaseButton>
      </div>
    </BaseModal>

    <BaseModal v-model="open" title="Connect your Stripe account" @update:model-value="(v: boolean) => !v && closeDialog()">
      <form style="display: flex; flex-direction: column; gap: var(--ds-space-4)" autocomplete="off" @submit.prevent="submit">
        <p class="ds-meta" style="margin: 0">
          In Stripe, open Developers, API keys, and copy your <strong>secret key</strong> (sk_…), or create a <strong>restricted key</strong> (rk_…) that allows: Checkout Sessions (write), Refunds
          (write) and Webhook Endpoints (write). Paste it here. It is checked with Stripe, then stored encrypted. Nobody can read it back, not
          even you; to change it you paste it again. Use a test key (sk_test_… or rk_test_…) to try it without real money, a live key (sk_live_… or rk_live_…) for real
          payments.
        </p>
        <div v-if="errors._" class="ds-alert ds-alert-danger stripe-error"><div>{{ errors._ }}</div></div>
        <label class="ds-field">
          <span class="ds-field-label">Stripe key</span>
          <input v-model="secretKey" type="password" class="ds-input" autocomplete="new-password" placeholder="sk_test_… or rk_test_…" aria-label="Stripe key" />
          <span v-if="errors.secret_key" class="ds-field-error">{{ errors.secret_key }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Webhook signing secret (optional)</span>
          <input v-model="webhookSecret" type="password" class="ds-input" autocomplete="new-password" placeholder="whsec_…" aria-label="Webhook signing secret" />
          <span class="ds-meta">From a Stripe webhook endpoint pointing to this site's /api/webhooks/stripe, or from the Stripe CLI. Left empty, it is registered for you on a public https site.</span>
          <span v-if="errors.webhook_secret" class="ds-field-error">{{ errors.webhook_secret }}</span>
        </label>
        <p class="ds-meta" style="margin: 0">
          The payment methods on the Stripe page (cards, Klarna, Link, wallets…) are chosen in your Stripe account, under Settings, Payment methods. Switch off the ones you do not want.
        </p>
        <fieldset class="ds-field" style="border: 0; padding: 0; margin: 0">
          <span class="ds-field-label">Tax</span>
          <label class="ds-checkbox" style="align-items: center">
            <input v-model="managedPayments" type="checkbox" aria-label="Use Stripe Managed Payments" />
            <span class="ds-checkbox-box">✓</span>
            <span class="ds-meta">Use Stripe Managed Payments (Stripe handles the tax). Unticked, customers pay exactly the price shown and you handle tax yourself.</span>
          </label>
          <template v-if="managedPayments">
            <input v-model="taxCode" class="ds-input" autocomplete="off" placeholder="txcd_…" aria-label="Product tax code" />
            <span class="ds-meta">Stripe needs a product tax code on every payment (find it in Stripe, Product tax codes).</span>
            <span v-if="errors.tax_code" class="ds-field-error">{{ errors.tax_code }}</span>
          </template>
        </fieldset>
        <p v-if="secretKey.includes('_live_')" class="ds-meta" style="margin: 0">Live key: real customers will pay real money into this account.</p>
        <div style="display: flex; gap: var(--ds-space-2); justify-content: flex-end">
          <BaseButton type="button" variant="secondary" :disabled="saving" @click="closeDialog">Cancel</BaseButton>
          <BaseButton type="submit" class="stripe-save" :disabled="saving || !secretKey.trim()">{{ saving ? 'Testing with Stripe…' : 'Test and save' }}</BaseButton>
        </div>
      </form>
    </BaseModal>
  </section>
</template>
