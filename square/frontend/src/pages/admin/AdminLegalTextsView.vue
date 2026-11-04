<script setup lang="ts">
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import { ref, onMounted } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import { fetchAdminSettings, updateAdminSettings, ValidationError } from '../../services/adminSettingsApi'
import { useToast } from '../../composables/useToast'

// The square's own Privacy Policy and Terms of Sale (rootsquares W6-R51). Plain text; line breaks are kept on the public pages.
const toast = useToast()

const loading = ref(true)
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const form = ref({ privacy_text: '', terms_text: '' })

async function load() {
  loading.value = true
  const settings = await fetchAdminSettings()
  form.value = { privacy_text: settings.privacy_text ?? '', terms_text: settings.terms_text ?? '' }
  loading.value = false
}

// Sends only the two texts, so saving here can never overwrite other settings changed on another page.
async function save() {
  saving.value = true
  errors.value = {}
  try {
    const settings = await updateAdminSettings({ ...form.value })
    form.value = { privacy_text: settings.privacy_text ?? '', terms_text: settings.terms_text ?? '' }
    toast.success('Legal texts saved')
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save the legal texts')
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div class="ds-heading">
      <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
      <h1 class="ds-display ds-display-s">Settings</h1>
      <p class="ds-intro">Site-wide settings and content that do not change often.</p>
    </div>

    <SettingsSectionNav />

    <div style="max-width: 760px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <h2 class="ds-display ds-display-s">Legal texts</h2>
        <SettingsBackButton />
      </div>

      <BaseLoadingState v-if="loading" label="Loading legal texts…" />
      <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <p class="ds-meta">
          Shown on the public Privacy Policy and Terms of Sale pages. Leave a text empty and that page says it has not been published yet.
          rootsquares does not write these for you: have them checked by someone qualified for your country.
        </p>

        <label class="ds-field">
          <span class="ds-field-label">Privacy Policy</span>
          <span class="ds-textarea-control">
            <textarea v-model="form.privacy_text" rows="12" maxlength="30000" class="ds-textarea" aria-label="Privacy Policy text"></textarea>
          </span>
          <span v-if="errors.privacy_text" class="ds-field-error-text">{{ errors.privacy_text }}</span>
        </label>
        <label class="ds-field">
          <span class="ds-field-label">Terms of Sale</span>
          <span class="ds-textarea-control">
            <textarea v-model="form.terms_text" rows="12" maxlength="30000" class="ds-textarea" aria-label="Terms of Sale text"></textarea>
          </span>
          <span v-if="errors.terms_text" class="ds-field-error-text">{{ errors.terms_text }}</span>
        </label>

        <BaseButton type="button" style="align-self: flex-start" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </BaseButton>
      </div>
    </div>
  </div>
</template>
