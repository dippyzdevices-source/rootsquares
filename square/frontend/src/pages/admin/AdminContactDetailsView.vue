<script setup lang="ts">
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import { computed, ref, onMounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import {
  fetchAdminSettings,
  updateAdminSettings,
  ValidationError,
} from '../../services/adminSettingsApi'
import { useToast } from '../../composables/useToast'

const toast = useToast()

const loading = ref(true)
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const form = ref({ contact_email: '', contact_phone: '', contact_address: '', timezone: 'Europe/Oslo' })
// Every time zone this browser knows; the saved one is always offered, even if the list lacks it.
const zones = computed(() => {
  const all = typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : []
  return all.includes(form.value.timezone) ? all : [form.value.timezone, ...all]
})

async function load() {
  loading.value = true
  const settings = await fetchAdminSettings()
  form.value = {
    contact_email: settings.contact_email,
    contact_phone: settings.contact_phone,
    contact_address: settings.contact_address,
    timezone: settings.timezone ?? 'Europe/Oslo',
  }
  loading.value = false
}

// Sends only the contact fields and the time zone, so saving here can never overwrite the site-availability
// settings (which live on their own page and may have been changed since this page loaded).
async function save() {
  saving.value = true
  errors.value = {}
  try {
    const settings = await updateAdminSettings({ ...form.value })
    form.value = {
      contact_email: settings.contact_email,
      contact_phone: settings.contact_phone,
      contact_address: settings.contact_address,
      timezone: settings.timezone ?? form.value.timezone,
    }
    toast.success('Contact details saved')
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save contact details')
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Settings</h1>
        <p class="ds-intro">Site-wide settings and content that do not change often.</p>
      </div>
    </div>

    <SettingsSectionNav />

    <div style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <h2 class="ds-display ds-display-s">Contact details</h2>
        <SettingsBackButton />
      </div>

      <BaseLoadingState v-if="loading" label="Loading contact details…" />
      <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <div>
          <h2 class="ds-title">Public contact details</h2>
          <p class="ds-meta">
            Shown on the public Contact page — update this instead of the code when the
            association's email, phone, or address changes.
          </p>
        </div>

        <label class="ds-field">
          <span class="ds-field-label">Email</span>
          <span class="ds-field-control"><input v-model="form.contact_email" type="text" class="ds-field-input" /></span>
          <span v-if="errors.contact_email" class="ds-field-error-text">{{ errors.contact_email }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Phone</span>
          <span class="ds-field-control"><input v-model="form.contact_phone" type="text" class="ds-field-input" /></span>
          <span v-if="errors.contact_phone" class="ds-field-error-text">{{ errors.contact_phone }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Address</span>
          <span class="ds-field-control"><input v-model="form.contact_address" type="text" class="ds-field-input" /></span>
          <span v-if="errors.contact_address" class="ds-field-error-text">{{ errors.contact_address }}</span>
        </label>
        <div>
          <BaseSelect
            v-model="form.timezone"
            label="Time zone"
            hint='Decides what "the event day" means, for example when refunds stop.'
            :options="zones"
          />
          <span v-if="errors.timezone" class="ds-field-error-text">{{ errors.timezone }}</span>
        </div>

        <BaseButton type="button" style="align-self: flex-start" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </BaseButton>
      </div>
    </div>
  </div>
</template>
