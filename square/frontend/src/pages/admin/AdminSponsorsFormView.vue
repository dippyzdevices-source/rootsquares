<script setup lang="ts">
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import {
  fetchAdminSponsor,
  createAdminSponsor,
  updateAdminSponsor,
  uploadAdminSponsorLogo,
  ValidationError,
  type AdminSponsor,
  type SponsorPayload,
} from '../../services/adminSponsorsApi'
import { useToast } from '../../composables/useToast'

const route = useRoute()
const toast = useToast()

// Id of a record created on this page. The URL is swapped to /edit with history.replaceState, which
// does not change route.params, so without this a second Save would create a duplicate.
const createdId = ref<number | null>(null)
const sponsorId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : createdId.value
})
const isEditing = computed(() => sponsorId.value !== null)

const loading = ref(isEditing.value)
const saving = ref(false)
const uploading = ref(false)
const errors = ref<Record<string, string>>({})
const sponsor = ref<AdminSponsor | null>(null)
// Logo picked on the create form; uploaded right after the sponsor row exists.
const pendingLogo = ref<File | null>(null)

const form = ref({
  name: '',
  website_url: '',
  display_order: '0',
  is_active: true,
})

async function loadSponsor() {
  if (sponsorId.value === null) return
  try {
    sponsor.value = await fetchAdminSponsor(sponsorId.value)
    form.value = {
      name: sponsor.value.name,
      website_url: sponsor.value.website_url ?? '',
      display_order: String(sponsor.value.display_order),
      is_active: sponsor.value.is_active,
    }
  } catch {
    toast.error('Could not load this sponsor')
  } finally {
    loading.value = false
  }
}

onMounted(loadSponsor)

function buildPayload(): SponsorPayload {
  return {
    name: form.value.name,
    website_url: form.value.website_url.trim() || null,
    display_order: Number(form.value.display_order) || 0,
    is_active: form.value.is_active,
  }
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    if (isEditing.value && sponsorId.value !== null) {
      sponsor.value = await updateAdminSponsor(sponsorId.value, buildPayload())
      toast.success('Sponsor updated')
    } else {
      sponsor.value = await createAdminSponsor(buildPayload())
      createdId.value = sponsor.value.id
      history.replaceState(null, '', `/admin/content/sponsors/${sponsor.value.id}/edit`)
      if (pendingLogo.value) {
        try {
          sponsor.value = await uploadAdminSponsorLogo(sponsor.value.id, pendingLogo.value)
          toast.success('Sponsor created')
        } catch {
          toast.error('Sponsor created, but the logo could not be uploaded — try again below')
        }
        pendingLogo.value = null
      } else {
        toast.success('Sponsor created')
      }
    }
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save this sponsor')
    }
  } finally {
    saving.value = false
  }
}

async function onLogoSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!sponsor.value) {
    pendingLogo.value = file
    return
  }

  uploading.value = true
  try {
    sponsor.value = await uploadAdminSponsorLogo(sponsor.value.id, file)
    toast.success('Logo uploaded')
  } catch (err) {
    toast.error(err instanceof ValidationError && err.errors.file ? err.errors.file : 'Could not upload this logo')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Settings</h1>
        <p class="ds-intro">Site-wide settings and content that do not change often.</p>
      </div>
      <BaseButton type="button" to="/admin/content/sponsors" variant="secondary" size="sm">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
        Back
      </BaseButton>
    </div>

    <SettingsSectionNav />

    <div style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <h2 class="ds-display ds-display-s">{{ isEditing ? 'Edit sponsor' : 'New sponsor' }}</h2>

      <BaseLoadingState v-if="loading" label="Loading sponsor…" />
      <template v-else>
        <div class="ds-card" style="display: flex; align-items: center; gap: var(--ds-space-4)">
          <div style="width: 160px; height: 80px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; border: 1px solid var(--ds-border-hairline); border-radius: var(--ds-radius-md, 8px); overflow: hidden">
            <img v-if="sponsor?.logo_url" :src="sponsor.logo_url" :alt="sponsor.name" style="max-width: 100%; max-height: 100%; object-fit: contain" />
            <span v-else class="ds-caption">{{ pendingLogo ? pendingLogo.name : 'No logo' }}</span>
          </div>
          <div>
            <label class="ds-field-label" style="cursor: pointer">
              {{ uploading ? 'Uploading…' : 'Upload logo' }}
              <input type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" style="display: none" :disabled="uploading" @change="onLogoSelected" />
            </label>
            <p class="ds-caption" style="margin-top: 4px">JPEG, PNG, or WebP. A wide logo on a transparent or white background works best.</p>
          </div>
        </div>

        <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <label class="ds-field">
            <span class="ds-field-label">Name</span>
            <span class="ds-field-control"><input v-model="form.name" type="text" placeholder="Acme AS" class="ds-field-input" /></span>
            <span v-if="errors.name" class="ds-field-error-text">{{ errors.name }}</span>
          </label>

          <label class="ds-field">
            <span class="ds-field-label">Website (optional)</span>
            <span class="ds-field-control"><input v-model="form.website_url" type="url" placeholder="https://example.no" class="ds-field-input" /></span>
            <span class="ds-field-hint">The logo links here when clicked.</span>
            <span v-if="errors.website_url" class="ds-field-error-text">{{ errors.website_url }}</span>
          </label>

          <label class="ds-field">
            <span class="ds-field-label">Display order</span>
            <span class="ds-field-control"><input v-model="form.display_order" type="number" class="ds-field-input" /></span>
            <span class="ds-field-hint">Lower numbers appear first.</span>
            <span v-if="errors.display_order" class="ds-field-error-text">{{ errors.display_order }}</span>
          </label>

          <label class="ds-checkbox">
            <input v-model="form.is_active" type="checkbox" />
            <span class="ds-checkbox-box">✓</span>
            <span class="ds-checkbox-label">Active (shown on the home page)</span>
          </label>

          <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
            <BaseButton to="/admin/content/sponsors" variant="ghost">Cancel</BaseButton>
            <BaseButton type="button" class="save-sponsor" :disabled="saving" @click="save">
              {{ saving ? 'Saving…' : 'Save' }}
            </BaseButton>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
