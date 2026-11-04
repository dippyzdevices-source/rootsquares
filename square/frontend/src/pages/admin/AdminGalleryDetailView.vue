<script setup lang="ts">
import { moduleEnabled } from '../../services/modules'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseFileButton from '../../components/ui/BaseFileButton.vue'
import DescriptionStyleSelect from '../../components/ui/DescriptionStyleSelect.vue'
import BaseEmptyState from '../../components/ui/BaseEmptyState.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import {
  fetchAdminAlbum,
  createAdminAlbum,
  updateAdminAlbum,
  uploadMedia,
  updateMediaCaption,
  deleteMedia,
  ValidationError,
  type AdminAlbum,
  type AlbumPayload,
} from '../../services/adminGalleryApi'
import { fetchAdminEvents, type AdminEvent } from '../../services/adminEventsApi'
import { useLookup } from '../../composables/useLookup'
import type { DescriptionStyle } from '../../services/settingsApi'
import { useToast } from '../../composables/useToast'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const { options: albumCategories } = useLookup('album_category')

const albumId = computed(() => {
  const id = route.params.id
  return id && id !== 'new' ? Number(id) : null
})
const isEditing = computed(() => albumId.value !== null)

const loading = ref(isEditing.value)
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const album = ref<AdminAlbum | null>(null)
const events = ref<AdminEvent[]>([])
const uploading = ref(false)
const uploadErrors = ref<{ filename: string; error: string }[]>([])

const form = ref({ title: '', description: '', description_style: '', event_id: '', category: '', year: String(new Date().getFullYear()), published: false })

const eventOptions = computed(() => [
  { value: '', label: 'None' },
  ...events.value.map((event) => ({ value: String(event.id), label: event.title })),
])

async function loadEvents() {
  if (!moduleEnabled('events')) return // W8-R28: the related-event picker belongs to the Events module
  try {
    const data = await fetchAdminEvents()
    events.value = data.items
  } catch {
    // The event picker is a convenience; a failed fetch just leaves it at "None".
  }
}

async function load() {
  loading.value = true
  if (albumId.value === null) {
    album.value = null
    loading.value = false
    return
  }
  try {
    album.value = await fetchAdminAlbum(albumId.value)
    form.value = {
      title: album.value.title,
      description: album.value.description ?? '',
      description_style: album.value.description_style ?? '',
      event_id: album.value.event_id != null ? String(album.value.event_id) : '',
      category: album.value.category ?? '',
      year: String(album.value.year),
      published: album.value.published,
    }
  } catch {
    toast.error('Could not load this album')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadEvents()
  await load()
})

// A router.push from /admin/gallery/new to /admin/gallery/:id (after creating an album)
// reuses this same component instance — onMounted never re-fires — so the newly created
// album's data (and its Photos section) must be loaded reactively off the route param too.
watch(() => route.params.id, load)

function buildPayload(): AlbumPayload {
  return {
    title: form.value.title,
    description: form.value.description || null,
    description_style: (form.value.description_style || null) as DescriptionStyle | null,
    event_id: form.value.event_id ? Number(form.value.event_id) : null,
    category: form.value.category || null,
    year: form.value.year ? Number(form.value.year) : null,
    published: form.value.published,
  }
}

async function saveAlbum() {
  saving.value = true
  errors.value = {}
  try {
    if (isEditing.value && albumId.value !== null) {
      album.value = await updateAdminAlbum(albumId.value, buildPayload())
      toast.success('Album updated')
    } else {
      const created = await createAdminAlbum(buildPayload())
      toast.success('Album created')
      router.push(`/admin/gallery/${created.id}`)
    }
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save this album')
    }
  } finally {
    saving.value = false
  }
}

// Photos go up one at a time: a single request holding dozens of photos is slow, can hit size
// limits, and one failure used to lose the whole batch with no reason shown. Each file now
// succeeds or fails on its own, with its own reason, and failed ones can be retried.
const uploadProgress = ref<{ done: number; total: number } | null>(null)
const failedFiles = ref<File[]>([])

async function uploadFiles(files: File[]) {
  if (albumId.value === null || files.length === 0) return
  uploading.value = true
  uploadErrors.value = []
  failedFiles.value = []
  uploadProgress.value = { done: 0, total: files.length }
  let uploaded = 0

  for (const file of files) {
    try {
      const result = await uploadMedia(albumId.value, [file])
      uploaded += result.created.length
      if (result.errors.length > 0) {
        uploadErrors.value.push(...result.errors)
        failedFiles.value.push(file)
      }
    } catch (err) {
      uploadErrors.value.push({
        filename: file.name,
        error: err instanceof Error ? err.message : 'Upload failed.',
      })
      failedFiles.value.push(file)
    }
    uploadProgress.value = { done: uploadProgress.value.done + 1, total: files.length }
  }

  try {
    album.value = await fetchAdminAlbum(albumId.value)
  } catch {
    // The photos are uploaded either way; a failed refresh just leaves the grid stale.
  }
  if (uploaded > 0) toast.success(`Uploaded ${uploaded} of ${files.length} photo(s)`)
  if (failedFiles.value.length > 0) toast.error(`${failedFiles.value.length} photo(s) failed — see the list below`)
  uploadProgress.value = null
  uploading.value = false
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files ? Array.from(input.files) : []
  input.value = ''
  await uploadFiles(files)
}

function retryFailed() {
  return uploadFiles([...failedFiles.value])
}

async function removeMedia(mediaId: number) {
  if (albumId.value === null) return
  try {
    await deleteMedia(mediaId)
    album.value = await fetchAdminAlbum(albumId.value)
    toast.success('Photo removed')
  } catch {
    toast.error('Could not remove this photo')
  }
}

async function saveCaption(mediaId: number, caption: string) {
  try {
    await updateMediaCaption(mediaId, caption || null)
    if (album.value) {
      const photo = album.value.media.find((m) => m.id === mediaId)
      if (photo) photo.caption = caption || null
    }
  } catch {
    toast.error('Could not save this caption')
  }
}
</script>

<template>
  <div class="ds-scope" style="display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ds-space-4); flex-wrap: wrap">
      <div class="ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
        <h1 class="ds-display ds-display-s">Gallery</h1>
      </div>
      <BaseButton type="button" to="/admin/gallery" variant="secondary" size="sm">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
        Back
      </BaseButton>
    </div>

    <hr class="ds-section-line" />

    <div style="max-width: 720px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
      <div>
        <h2 class="ds-display ds-display-s">{{ isEditing ? 'Edit album' : 'New album' }}</h2>
        <p v-if="album?.created_by_email || album?.updated_by_email" class="ds-meta">
          <span v-if="album.created_by_email">Created by {{ album.created_by_email }}</span>
          <span v-if="album.created_by_email && album.updated_by_email"> · </span>
          <span v-if="album.updated_by_email">Last edited by {{ album.updated_by_email }}</span>
        </p>
      </div>

    <BaseLoadingState v-if="loading" label="Loading album…" />
    <template v-else>
      <div class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
        <label class="ds-field">
          <span class="ds-field-label">Title</span>
          <span class="ds-field-control"><input v-model="form.title" type="text" class="ds-field-input" /></span>
          <span v-if="errors.title" class="ds-field-error-text">{{ errors.title }}</span>
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Description</span>
          <span class="ds-textarea-control">
            <textarea v-model="form.description" rows="3" class="ds-textarea"></textarea>
          </span>
        </label>

        <DescriptionStyleSelect v-model="form.description_style" what="album" :error="errors.description_style" />

        <label class="ds-field">
          <span class="ds-field-label">Year of the photos *</span>
          <span class="ds-field-control"><input v-model="form.year" type="number" min="1900" required class="ds-field-input year-input" /></span>
          <span v-if="errors.year" class="ds-field-error-text">{{ errors.year }}</span>
        </label>

        <label v-if="moduleEnabled('events')" class="ds-field">
          <span class="ds-field-label">Related event (optional)</span>
          <BaseSelect v-model="form.event_id" :options="eventOptions" />
        </label>

        <label class="ds-field">
          <span class="ds-field-label">Category (optional)</span>
          <BaseSelect v-model="form.category" :options="[{ value: '', label: 'None' }, ...albumCategories]" />
          <span v-if="errors.category" class="ds-field-error-text">{{ errors.category }}</span>
        </label>

        <label class="ds-checkbox">
          <input v-model="form.published" type="checkbox" />
          <span class="ds-checkbox-box">✓</span>
          <span class="ds-checkbox-label">Published</span>
        </label>

        <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
          <BaseButton to="/admin/gallery" variant="ghost" size="md">Cancel</BaseButton>
          <BaseButton
            type="button"
            variant="primary"
            size="md"
            class="save-album"
            :disabled="saving"
            @click="saveAlbum"
          >
            {{ saving ? 'Saving…' : 'Save' }}
          </BaseButton>
        </div>
      </div>

      <section v-if="isEditing && album" style="display: flex; flex-direction: column; gap: var(--ds-space-3)">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--ds-space-3)">
          <h2 class="ds-title">Photos</h2>
          <BaseFileButton size="sm" multiple accept="image/jpeg,image/png,image/webp,image/heic,image/heif" :disabled="uploading" @change="handleFileSelect">
            {{ uploadProgress ? `Uploading ${uploadProgress.done} of ${uploadProgress.total}…` : uploading ? 'Uploading…' : 'Add photos' }}
          </BaseFileButton>
        </div>

        <div v-if="uploadErrors.length" class="ds-alert ds-alert-danger">
          <div>
            <div v-for="(err, i) in uploadErrors" :key="err.filename + i">{{ err.filename }}: {{ err.error }}</div>
            <BaseButton v-if="failedFiles.length && !uploading" type="button" variant="secondary" size="sm" style="margin-top: var(--ds-space-3)" @click="retryFailed">
              Retry {{ failedFiles.length }} failed
            </BaseButton>
          </div>
        </div>

        <BaseEmptyState
          v-if="album.media.length === 0"
          title="No photos yet"
          description="Add photos using the button above."
        />
        <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--ds-space-4)">
          <div v-for="photo in album.media" :key="photo.id" style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
            <div class="ds-rect" style="position: relative; aspect-ratio: 1 / 1">
              <div class="ds-rect-inner">
                <img
                  :src="photo.thumbnail_url"
                  :alt="photo.filename"
                  style="width: 100%; height: 100%; object-fit: cover"
                />
              </div>
              <BaseIconButton variant="danger" size="sm" :label="`Delete ${photo.filename}`" style="position: absolute; top: var(--ds-space-2); right: var(--ds-space-2)" @click="removeMedia(photo.id)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></svg>
              </BaseIconButton>
            </div>
            <span class="ds-field-control">
              <input
                :value="photo.caption ?? ''"
                type="text"
                placeholder="Add a caption…"
                class="ds-field-input"
                @change="saveCaption(photo.id, ($event.target as HTMLInputElement).value)"
              />
            </span>
          </div>
        </div>
      </section>
    </template>
    </div>
  </div>
</template>
