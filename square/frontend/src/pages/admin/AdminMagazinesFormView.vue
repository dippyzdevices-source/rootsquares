<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import DescriptionStyleSelect from '../../components/ui/DescriptionStyleSelect.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import {
  fetchAdminMagazine,
  createAdminMagazine,
  updateAdminMagazine,
  uploadAdminMagazinePdf,
  uploadAdminMagazineCover,
  ValidationError,
  type AdminMagazine,
  type MagazinePayload,
} from '../../services/adminMagazinesApi'
import { renderFirstPageToBlob } from '../../utils/pdfjs'
import type { DescriptionStyle } from '../../services/settingsApi'
import { useToast } from '../../composables/useToast'

const MAX_PDF_BYTES = 25 * 1024 * 1024

const route = useRoute()
const toast = useToast()

// Id of a record created on this page. The URL is swapped to /edit with history.replaceState, which
// does not change route.params, so without this a second Save would create a duplicate.
const createdId = ref<number | null>(null)
const magazineId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : createdId.value
})
const isEditing = computed(() => magazineId.value !== null)

const loading = ref(isEditing.value)
const saving = ref(false)
const busy = ref<'pdf' | 'cover' | null>(null)
const errors = ref<Record<string, string>>({})
const magazine = ref<AdminMagazine | null>(null)
// Files picked on the create form; uploaded right after the magazine row exists.
const pendingPdf = ref<File | null>(null)
const pendingCover = ref<File | null>(null)

const form = ref({
  title: '',
  issue_label: '',
  issue_date: '',
  description: '',
  description_style: '',
  published: false,
})

async function loadMagazine() {
  if (magazineId.value === null) return
  try {
    magazine.value = await fetchAdminMagazine(magazineId.value)
    form.value = {
      title: magazine.value.title,
      issue_label: magazine.value.issue_label ?? '',
      issue_date: magazine.value.issue_date ?? '',
      description: magazine.value.description ?? '',
      description_style: magazine.value.description_style ?? '',
      published: magazine.value.published,
    }
  } catch {
    toast.error('Could not load this magazine')
  } finally {
    loading.value = false
  }
}

onMounted(loadMagazine)

function buildPayload(): MagazinePayload {
  return {
    title: form.value.title,
    issue_label: form.value.issue_label.trim() || null,
    issue_date: form.value.issue_date || null,
    description: form.value.description.trim() || null,
    description_style: (form.value.description_style || null) as DescriptionStyle | null,
    ...(isEditing.value ? { published: form.value.published } : {}),
  }
}

function pdfProblem(file: File): string | null {
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) return 'Choose a PDF file.'
  if (file.size > MAX_PDF_BYTES) return 'The PDF is too large (limit 25MB).'
  return null
}

// Uploads the PDF, then generates the cover from its first page when the magazine has none.
async function uploadPdf(id: number, file: File) {
  busy.value = 'pdf'
  try {
    magazine.value = await uploadAdminMagazinePdf(id, file)
    toast.success('PDF uploaded')
  } catch (err) {
    toast.error(err instanceof ValidationError && err.errors.file ? err.errors.file : 'Could not upload this PDF')
    busy.value = null
    return
  }
  if (!magazine.value?.cover_url) {
    busy.value = 'cover'
    try {
      const blob = await renderFirstPageToBlob(file)
      magazine.value = await uploadAdminMagazineCover(id, new File([blob], 'cover.jpg', { type: 'image/jpeg' }))
      toast.success('Cover generated from page 1')
    } catch {
      toast.error('Could not generate a cover from the PDF, upload one instead')
    }
  }
  busy.value = null
}

async function uploadCover(id: number, file: File) {
  busy.value = 'cover'
  try {
    magazine.value = await uploadAdminMagazineCover(id, file)
    toast.success('Cover uploaded')
  } catch (err) {
    toast.error(err instanceof ValidationError && err.errors.file ? err.errors.file : 'Could not upload this cover')
  } finally {
    busy.value = null
  }
}

async function onPdfSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const problem = pdfProblem(file)
  if (problem) {
    toast.error(problem)
    return
  }
  if (magazine.value) await uploadPdf(magazine.value.id, file)
  else pendingPdf.value = file
}

async function onCoverSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (magazine.value) await uploadCover(magazine.value.id, file)
  else pendingCover.value = file
}

async function regenerateCover() {
  if (!magazine.value?.pdf_url) return
  busy.value = 'cover'
  try {
    const blob = await renderFirstPageToBlob(magazine.value.pdf_url)
    magazine.value = await uploadAdminMagazineCover(magazine.value.id, new File([blob], 'cover.jpg', { type: 'image/jpeg' }))
    toast.success('Cover generated from page 1')
  } catch {
    toast.error('Could not generate a cover from the PDF')
  } finally {
    busy.value = null
  }
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    if (isEditing.value && magazineId.value !== null) {
      magazine.value = await updateAdminMagazine(magazineId.value, buildPayload())
      toast.success('Magazine updated')
      form.value.published = magazine.value.published
    } else {
      magazine.value = await createAdminMagazine(buildPayload())
      createdId.value = magazine.value.id
      history.replaceState(null, '', `/admin/news/magazines/${magazine.value.id}/edit`)
      toast.success('Magazine created')
      const id = magazine.value.id
      if (pendingPdf.value) await uploadPdf(id, pendingPdf.value)
      if (pendingCover.value) await uploadCover(id, pendingCover.value)
      pendingPdf.value = null
      pendingCover.value = null
    }
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
      if (err.errors.published) form.value.published = false
    } else {
      toast.error('Could not save this magazine')
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Magazines</h1>
      </div>
      <BaseButton type="button" to="/admin/news/magazines" variant="secondary" size="sm">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
        Back
      </BaseButton>
    </div>

    <hr class="ds-section-line" />

    <div style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <h2 class="ds-display ds-display-s">{{ isEditing ? 'Edit magazine' : 'New magazine' }}</h2>

      <BaseLoadingState v-if="loading" label="Loading magazine…" />
      <template v-else>
        <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <div style="display: flex; align-items: center; gap: var(--ds-space-4)">
            <div style="width: 96px; aspect-ratio: 3 / 4; flex-shrink: 0; display: flex; align-items: center; justify-content: center; border: 1px solid var(--ds-border-hairline); border-radius: 6px; overflow: hidden">
              <img v-if="magazine?.cover_url" :src="magazine.cover_url" :alt="magazine.title" style="width: 100%; height: 100%; object-fit: cover" />
              <span v-else class="ds-caption" style="text-align: center; padding: 4px">{{ pendingCover ? pendingCover.name : 'No cover' }}</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
              <label class="ds-field-label" style="cursor: pointer">
                {{ busy === 'cover' ? 'Working…' : 'Upload cover' }}
                <input type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" style="display: none" :disabled="busy !== null" @change="onCoverSelected" />
              </label>
              <button v-if="magazine?.pdf_url" type="button" class="ds-field-label regenerate-cover" style="cursor: pointer; text-align: left; background: none; border: none; padding: 0" :disabled="busy !== null" @click="regenerateCover">
                Use page 1 of the PDF as cover
              </button>
              <p class="ds-caption">Optional. Without one, page 1 of the PDF is used.</p>
            </div>
          </div>

          <hr class="ds-section-line" />

          <div style="display: flex; flex-direction: column; gap: var(--ds-space-1)">
            <span class="ds-field-label">PDF</span>
            <p v-if="magazine?.pdf_url" class="ds-meta">
              <a :href="magazine.pdf_url" target="_blank" rel="noopener" style="text-decoration: underline">Current PDF</a>
              — choose a file below to replace it.
            </p>
            <p v-else-if="pendingPdf" class="ds-meta">Selected: {{ pendingPdf.name }} (uploaded when you save)</p>
            <label class="ds-field-label" style="cursor: pointer">
              {{ busy === 'pdf' ? 'Uploading…' : magazine?.pdf_url ? 'Replace PDF' : 'Choose PDF' }}
              <input type="file" accept="application/pdf,.pdf" style="display: none" :disabled="busy !== null" @change="onPdfSelected" />
            </label>
            <p class="ds-caption">PDF only, up to 25MB.</p>
            <span v-if="errors.file" class="ds-field-error-text">{{ errors.file }}</span>
          </div>
        </div>

        <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <label class="ds-field">
            <span class="ds-field-label">Title</span>
            <span class="ds-field-control"><input v-model="form.title" type="text" placeholder="Summer Special" class="ds-field-input" /></span>
            <span v-if="errors.title" class="ds-field-error-text">{{ errors.title }}</span>
          </label>

          <label class="ds-field">
            <span class="ds-field-label">Issue (optional)</span>
            <span class="ds-field-control"><input v-model="form.issue_label" type="text" placeholder="Summer 2026" class="ds-field-input" /></span>
            <span v-if="errors.issue_label" class="ds-field-error-text">{{ errors.issue_label }}</span>
          </label>

          <label class="ds-field">
            <span class="ds-field-label">Issue date (optional)</span>
            <span class="ds-field-control"><input v-model="form.issue_date" type="date" class="ds-field-input" /></span>
            <span class="ds-field-hint">Newest issue date is listed first.</span>
            <span v-if="errors.issue_date" class="ds-field-error-text">{{ errors.issue_date }}</span>
          </label>

          <label class="ds-field">
            <span class="ds-field-label">Description (optional)</span>
            <span class="ds-textarea-control">
              <textarea v-model="form.description" rows="3" class="ds-textarea" placeholder="What is in this issue."></textarea>
            </span>
            <span v-if="errors.description" class="ds-field-error-text">{{ errors.description }}</span>
          </label>

          <DescriptionStyleSelect v-model="form.description_style" what="magazine" :error="errors.description_style" />

          <div v-if="isEditing">
            <label class="ds-checkbox">
              <input v-model="form.published" type="checkbox" />
              <span class="ds-checkbox-box">✓</span>
              <span class="ds-checkbox-label">Published (visible under News → Magazines)</span>
            </label>
            <span v-if="errors.published" class="ds-field-error-text">{{ errors.published }}</span>
          </div>
          <p v-else class="ds-caption">New magazines start as a draft. Publish once the PDF is uploaded.</p>

          <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
            <BaseButton to="/admin/news/magazines" variant="ghost">Cancel</BaseButton>
            <BaseButton type="button" class="save-magazine" :disabled="saving || busy !== null" @click="save">
              {{ saving ? 'Saving…' : 'Save' }}
            </BaseButton>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
