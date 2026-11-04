<script setup lang="ts">
import { ref, onMounted } from 'vue'
import BaseLoadingState from './ui/BaseLoadingState.vue'
import BaseButton from './ui/BaseButton.vue'
import { fetchAdminSettings, updateAdminSettings, uploadHeritageImage } from '../services/adminSettingsApi'
import { useToast } from '../composables/useToast'

const toast = useToast()
const imageUrl = ref<string | null>(null)
const loading = ref(true)
const uploading = ref(false)
const error = ref('')
const aboutText = ref('')
const savingText = ref(false)
const textError = ref('')

onMounted(async () => {
  try {
    const settings = await fetchAdminSettings()
    imageUrl.value = settings.heritage_image_url ?? null
    aboutText.value = settings.about_text ?? ''
  } catch {
    toast.error('Could not load the current image')
  } finally {
    loading.value = false
  }
})

// Sends only the About text, so saving here cannot overwrite settings changed on another page.
async function saveText() {
  savingText.value = true
  textError.value = ''
  try {
    aboutText.value = (await updateAdminSettings({ about_text: aboutText.value })).about_text ?? ''
    toast.success('About text saved')
  } catch (err) {
    const errors = (err as { errors?: Record<string, string> }).errors
    textError.value = errors?.about_text ?? 'Could not save the About text'
  } finally {
    savingText.value = false
  }
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    imageUrl.value = (await uploadHeritageImage(file)).heritage_image_url ?? null
    toast.success('About image updated')
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
    <BaseLoadingState v-if="loading" label="Loading image…" />
    <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <h3 class="ds-title">About: photo</h3>
      <div class="ds-arch" style="aspect-ratio: 16 / 11">
        <img v-if="imageUrl" :src="imageUrl" alt="Current About page image" class="ds-arch-inner" style="object-fit: cover" />
        <div v-else class="ds-arch-inner ds-placeholder"><span class="ds-placeholder-glyph">✺</span></div>
      </div>
      <div>
        <label class="ds-field-label" style="cursor: pointer">
          {{ uploading ? 'Uploading…' : imageUrl ? 'Replace image' : 'Upload image' }}
          <input type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" class="heritage-image-input" style="display: none" :disabled="uploading" @change="onFileSelected" />
        </label>
        <p class="ds-caption" style="margin-top: 4px">JPEG, PNG, or WebP. A landscape photo works best — it's shown at roughly 16:11.</p>
        <span v-if="error" class="ds-field-error-text">{{ error }}</span>
      </div>
    </div>

    <div v-if="!loading" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <h3 class="ds-title">About: story text</h3>
      <p class="ds-meta">Your story, shown on the public About page under the photo. Plain text; line breaks are kept. Leave it empty and the page says nothing has been added yet.</p>
      <label class="ds-field">
        <span class="ds-field-label">About text</span>
        <span class="ds-textarea-control">
          <textarea v-model="aboutText" rows="10" maxlength="30000" class="ds-textarea" aria-label="About text"></textarea>
        </span>
        <span v-if="textError" class="ds-field-error-text">{{ textError }}</span>
      </label>
      <BaseButton type="button" style="align-self: flex-start" :disabled="savingText" @click="saveText">{{ savingText ? 'Saving…' : 'Save' }}</BaseButton>
    </div>
  </div>
</template>
