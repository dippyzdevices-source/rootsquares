<script setup lang="ts">
import SettingsSectionNav from '../../components/SettingsSectionNav.vue'
import SettingsBackButton from '../../components/SettingsBackButton.vue'
import { ref, onMounted } from 'vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import BaseFileButton from '../../components/ui/BaseFileButton.vue'
import { fetchAdminSettings, uploadHeritageImage } from '../../services/adminSettingsApi'
import { useToast } from '../../composables/useToast'

const toast = useToast()
const imageUrl = ref<string | null>(null)
const loading = ref(true)
const uploading = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    imageUrl.value = (await fetchAdminSettings()).heritage_image_url ?? null
  } catch {
    toast.error('Could not load the current image')
  } finally {
    loading.value = false
  }
})

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    imageUrl.value = (await uploadHeritageImage(file)).heritage_image_url ?? null
    toast.success('Heritage image updated')
  } catch (err) {
    const errors = (err as { errors?: Record<string, string> }).errors
    error.value = errors?.file ?? 'Could not upload this image'
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
    </div>

    <SettingsSectionNav />

    <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
        <h2 class="ds-display ds-display-s">Heritage image</h2>
        <SettingsBackButton />
      </div>

    <BaseLoadingState v-if="loading" label="Loading image…" />
    <div v-else class="ds-card" style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <div class="ds-arch" style="aspect-ratio: 16 / 11">
        <img v-if="imageUrl" :src="imageUrl" alt="Current Heritage page image" class="ds-arch-inner" style="object-fit: cover" />
        <div v-else class="ds-arch-inner ds-placeholder"><span class="ds-placeholder-glyph">✺</span></div>
      </div>
      <div>
        <BaseFileButton accept="image/jpeg,image/png,image/webp,image/heic,image/heif" class="heritage-image-input" :disabled="uploading" @change="onFileSelected">{{ uploading ? 'Uploading…' : imageUrl ? 'Replace image' : 'Upload image' }}</BaseFileButton>
        <p class="ds-caption" style="margin-top: 4px">JPEG, PNG, or WebP. A landscape photo works best — it's shown at roughly 16:11.</p>
        <span v-if="error" class="ds-field-error-text">{{ error }}</span>
      </div>
    </div>
  </div>
</template>
