<script setup lang="ts">
import { onMounted, ref } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import BaseModal from './ui/BaseModal.vue'
import BaseSelect from './ui/BaseSelect.vue'
import {
  connectVipps,
  disconnectVipps,
  fetchProviders,
  ProviderKeysError,
  type ProviderStatus,
  type VippsKeys,
} from '../services/adminPaymentProvidersApi'
import { useToast } from '../composables/useToast'

const emit = defineEmits<{ changed: [connected: boolean] }>()
const toast = useToast()

const status = ref<ProviderStatus>({ provider: 'vipps', connected: false })
const canEdit = ref(false)
const loading = ref(true)
const open = ref(false)
const confirmReplace = ref(false)
const confirmDisconnect = ref(false)
const saving = ref(false)
const errors = ref<Record<string, string>>({})

const blank = (): VippsKeys => ({ client_id: '', client_secret: '', subscription_key: '', msn: '', mode: 'test' })
const form = ref<VippsKeys>(blank())

async function load() {
  try {
    const view = await fetchProviders()
    status.value = view.providers.vipps
    canEdit.value = view.can_edit
  } catch {
    status.value = { provider: 'vipps', connected: false }
  } finally {
    loading.value = false
  }
}

function openDialog() {
  form.value = blank() // keys are never shown again: replacing them means typing them again
  errors.value = {}
  open.value = true
}

function closeDialog() {
  open.value = false
  form.value = blank() // do not keep the secrets in memory longer than needed
}

async function submit() {
  saving.value = true
  errors.value = {}
  try {
    const view = await connectVipps(form.value)
    status.value = view.providers.vipps
    canEdit.value = view.can_edit
    closeDialog()
    toast.success('Vipps is connected')
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
    const view = await disconnectVipps()
    status.value = view.providers.vipps
    toast.success('Vipps is disconnected')
    emit('changed', status.value.connected)
  } catch (e) {
    toast.error(e instanceof ProviderKeysError ? e.message : 'Could not disconnect Vipps')
  }
}

onMounted(load)
</script>

<template>
  <section class="ds-card vipps-connect" data-testid="vipps-connect" style="padding: var(--ds-space-4) var(--ds-space-5)">
    <div style="display: flex; gap: var(--ds-space-3); align-items: center; flex-wrap: wrap; justify-content: space-between">
      <div style="min-width: 0">
        <strong>Your Vipps account</strong>
        <p class="ds-meta" style="margin: 2px 0 0">
          <template v-if="loading">Checking…</template>
          <template v-else-if="status.connected">
            Connected in {{ status.mode === 'production' ? 'production' : 'test' }} mode<template v-if="status.hint?.msn"> · merchant {{ status.hint.msn }}</template
            ><template v-if="status.hint?.client_id_last4"> · key ending {{ status.hint.client_id_last4 }}</template>
          </template>
          <template v-else>Not connected. Customers cannot pay in the Vipps app until you connect your own Vipps account.</template>
        </p>
        <p v-if="status.connected && !status.webhook_registered" class="ds-meta" style="margin: 2px 0 0">
          Payments are confirmed when the customer returns to the site and by a regular check.
        </p>
      </div>
      <div v-if="!loading && canEdit && !status.connected" style="display: flex; gap: var(--ds-space-2)">
        <BaseButton type="button" size="sm" class="vipps-open" @click="openDialog">Connect Vipps</BaseButton>
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
        <span class="ds-meta">Replace the keys with new ones, or disconnect Vipps so customers can no longer pay with it.</span>
        <div style="display: flex; gap: var(--ds-space-2)">
          <BaseButton type="button" size="sm" variant="secondary" class="vipps-open" @click="confirmReplace = true">Replace keys</BaseButton>
          <BaseButton type="button" size="sm" variant="danger" class="vipps-disconnect" @click="confirmDisconnect = true">Disconnect</BaseButton>
        </div>
      </div>
    </div>

    <BaseModal v-model="confirmReplace" title="Replace keys?">
      <p class="ds-body">The current keys stop working as soon as you save new ones. Only continue if you have the new keys ready.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="confirmReplace = false">Cancel</BaseButton>
        <BaseButton type="button" variant="danger" class="confirm-replace" @click="startReplace">Continue</BaseButton>
      </div>
    </BaseModal>
    <BaseModal v-model="confirmDisconnect" title="Disconnect Vipps?">
      <p class="ds-body">Paying in the Vipps app stops working on this site right away and the stored keys are deleted. Past payments and orders stay. To use Vipps again you must enter the keys again.</p>
      <div style="margin-top: var(--ds-space-4); display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton type="button" variant="ghost" @click="confirmDisconnect = false">Cancel</BaseButton>
        <BaseButton type="button" variant="danger" class="confirm-disconnect" @click="doDisconnect">Disconnect</BaseButton>
      </div>
    </BaseModal>

    <BaseModal v-model="open" title="Connect your Vipps account" @update:model-value="(v: boolean) => !v && closeDialog()">
      <form style="display: flex; flex-direction: column; gap: var(--ds-space-4)" autocomplete="off" @submit.prevent="submit">
        <p class="ds-meta" style="margin: 0">
          Copy these from your Vipps MobilePay portal (Developer, your sales unit, API keys). They are checked with Vipps, then stored encrypted.
          Nobody can read them back, not even you; to change them you type them again.
        </p>
        <div v-if="errors._" class="ds-alert ds-alert-danger vipps-error"><div>{{ errors._ }}</div></div>

        <div class="ds-field">
          <BaseSelect
            v-model="form.mode"
            label="Environment"
            aria-label="Environment"
            :options="[{ value: 'test', label: 'Test (no real money)' }, { value: 'production', label: 'Production (real money)' }]"
          />
          <span v-if="errors.mode" class="ds-field-error">{{ errors.mode }}</span>
          <span v-else class="ds-field-hint">Use the keys from the same environment. Test keys only work in test.</span>
        </div>
        <label class="ds-field">
          <span class="ds-field-label">Merchant serial number</span>
          <input v-model="form.msn" class="ds-input" inputmode="numeric" autocomplete="off" aria-label="Merchant serial number" />
          <span v-if="errors.msn" class="ds-field-error">{{ errors.msn }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Client ID</span>
          <input v-model="form.client_id" class="ds-input" autocomplete="off" aria-label="Client ID" />
          <span v-if="errors.client_id" class="ds-field-error">{{ errors.client_id }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Client secret</span>
          <input v-model="form.client_secret" type="password" class="ds-input" autocomplete="new-password" aria-label="Client secret" />
          <span v-if="errors.client_secret" class="ds-field-error">{{ errors.client_secret }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Subscription key (Ocp-Apim-Subscription-Key)</span>
          <input v-model="form.subscription_key" type="password" class="ds-input" autocomplete="new-password" aria-label="Subscription key" />
          <span v-if="errors.subscription_key" class="ds-field-error">{{ errors.subscription_key }}</span>
        </label>
        <p v-if="form.mode === 'production'" class="ds-meta" style="margin: 0">Production: real customers will pay real money into this account.</p>

        <div style="display: flex; gap: var(--ds-space-2); justify-content: flex-end">
          <BaseButton type="button" variant="secondary" :disabled="saving" @click="closeDialog">Cancel</BaseButton>
          <BaseButton type="submit" class="vipps-save" :disabled="saving">{{ saving ? 'Testing with Vipps…' : 'Test and save' }}</BaseButton>
        </div>
      </form>
    </BaseModal>
  </section>
</template>
