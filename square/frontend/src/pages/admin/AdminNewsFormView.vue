<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseIconButton from '../../components/ui/BaseIconButton.vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseFileButton from '../../components/ui/BaseFileButton.vue'
import DescriptionStyleSelect from '../../components/ui/DescriptionStyleSelect.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import RichTextEditor from '../../components/ui/RichTextEditor.vue'
import {
  fetchAdminNewsArticle,
  createAdminNews,
  updateAdminNews,
  uploadNewsBanner,
  addNewsImage,
  deleteNewsImage,
  ValidationError,
  type NewsPayload,
  type NewsImage,
} from '../../services/adminNewsApi'
import { fromDatetimeLocalValue, toDatetimeLocalValue } from '../../utils/date'
import type { DescriptionStyle } from '../../services/settingsApi'
import { useToast } from '../../composables/useToast'
import { useLookup } from '../../composables/useLookup'

const { label: newsStatusLabel } = useLookup('news_status')
const route = useRoute()
const router = useRouter()
const toast = useToast()

const newsId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})
const isEditing = computed(() => newsId.value !== null)

const loading = ref(isEditing.value)
const saving = ref(false)
const errors = ref<Record<string, string>>({})
const attribution = ref<{ created_by_email: string | null; updated_by_email: string | null } | null>(null)
const bannerImage = ref<string | null>(null)
const uploadingBanner = ref(false)
const images = ref<NewsImage[]>([])
const uploadingImage = ref(false)

const form = ref({
  title: '',
  summary: '',
  description_style: '',
  content: '',
  status: 'draft',
  category: '',
  author: '',
  published_at: '',
})

const statusOptions = computed(() => [
  { value: 'draft', label: newsStatusLabel('draft') },
  { value: 'published', label: newsStatusLabel('published') },
  { value: 'archived', label: newsStatusLabel('archived') },
])

const { options: categoryOptions } = useLookup('news_category')

onMounted(async () => {
  if (newsId.value === null) return
  try {
    const article = await fetchAdminNewsArticle(newsId.value)
    form.value = {
      title: article.title,
      summary: article.summary ?? '',
      description_style: article.description_style ?? '',
      content: article.content,
      status: article.status,
      category: article.category ?? '',
      author: article.author ?? '',
      published_at: article.published_at ? toDatetimeLocalValue(article.published_at) : '',
    }
    bannerImage.value = article.banner_image
    images.value = article.images ?? []
    attribution.value = {
      created_by_email: article.created_by_email,
      updated_by_email: article.updated_by_email,
    }
  } catch {
    toast.error('Could not load this article')
  } finally {
    loading.value = false
  }
})

async function handleBannerSelect(domEvent: Event) {
  if (newsId.value === null) return
  const input = domEvent.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  uploadingBanner.value = true
  try {
    const updated = await uploadNewsBanner(newsId.value, file)
    bannerImage.value = updated.banner_image
    toast.success('Banner updated')
  } catch {
    toast.error('Could not upload this banner image')
  } finally {
    uploadingBanner.value = false
    input.value = ''
  }
}

async function removeBanner() {
  if (newsId.value === null) return
  try {
    const updated = await updateAdminNews(newsId.value, { banner_image: null })
    bannerImage.value = updated.banner_image
    toast.success('Banner removed')
  } catch {
    toast.error('Could not remove this banner')
  }
}

async function handleAddImageSelect(domEvent: Event) {
  if (newsId.value === null) return
  const input = domEvent.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  uploadingImage.value = true
  try {
    const updated = await addNewsImage(newsId.value, file)
    images.value = updated.images
    toast.success('Image added')
  } catch {
    toast.error('Could not add this image')
  } finally {
    uploadingImage.value = false
    input.value = ''
  }
}

async function removeImage(imageId: number) {
  if (newsId.value === null) return
  try {
    const updated = await deleteNewsImage(newsId.value, imageId)
    images.value = updated.images
    toast.success('Image removed')
  } catch {
    toast.error('Could not remove this image')
  }
}

function buildPayload(): NewsPayload {
  return {
    title: form.value.title,
    summary: form.value.summary || null,
    description_style: (form.value.description_style || null) as DescriptionStyle | null,
    content: form.value.content,
    status: form.value.status,
    category: form.value.category || null,
    author: form.value.author || null,
    published_at: form.value.published_at ? fromDatetimeLocalValue(form.value.published_at) : null,
  }
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    if (isEditing.value && newsId.value !== null) {
      await updateAdminNews(newsId.value, buildPayload())
      toast.success('Article updated')
    } else {
      await createAdminNews(buildPayload())
      toast.success('Article created')
    }
    router.push('/admin/news')
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save this article')
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="ds-scope" style="max-width: 640px; display: flex; flex-direction: column; gap: var(--ds-space-6)">
    <div class="ds-heading">
      <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Admin console</span>
      <h1 class="ds-display ds-display-s">{{ isEditing ? 'Edit article' : 'New article' }}</h1>
      <p v-if="attribution?.created_by_email || attribution?.updated_by_email" class="ds-meta">
        <span v-if="attribution.created_by_email">Created by {{ attribution.created_by_email }}</span>
        <span v-if="attribution.created_by_email && attribution.updated_by_email"> · </span>
        <span v-if="attribution.updated_by_email">Last edited by {{ attribution.updated_by_email }}</span>
      </p>
    </div>

    <hr class="ds-section-line" />

    <BaseLoadingState v-if="loading" label="Loading article…" />
    <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <label class="ds-field">
        <span class="ds-field-label">Title</span>
        <span class="ds-field-control"><input v-model="form.title" type="text" placeholder="Article title" class="ds-field-input" /></span>
        <span v-if="errors.title" class="ds-field-error-text">{{ errors.title }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Summary</span>
        <span class="ds-textarea-control">
          <textarea v-model="form.summary" rows="2" class="ds-textarea"></textarea>
        </span>
        <span v-if="errors.summary" class="ds-field-error-text">{{ errors.summary }}</span>
      </label>

      <DescriptionStyleSelect v-model="form.description_style" what="article" :error="errors.description_style" />

      <div>
        <RichTextEditor v-model="form.content" label="Content" />
        <span v-if="errors.content" class="ds-field-error-text">{{ errors.content }}</span>
      </div>

      <div v-if="isEditing" style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
        <span class="ds-field-label">Banner image</span>
        <img
          v-if="bannerImage"
          :src="bannerImage"
          alt="Article banner"
          style="height: 128px; width: 100%; border-radius: var(--ds-radius-md); object-fit: cover"
        />
        <div style="display: flex; align-items: center; gap: var(--ds-space-3)">
          <BaseFileButton size="sm" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" :disabled="uploadingBanner" @change="handleBannerSelect">
            {{ uploadingBanner ? 'Uploading…' : bannerImage ? 'Replace banner' : 'Upload banner' }}
          </BaseFileButton>
          <BaseButton
            v-if="bannerImage"
            type="button"
            variant="ghost"
            size="sm"
            @click="removeBanner"
          >
            Remove
          </BaseButton>
        </div>
      </div>
      <p v-else class="ds-meta">Save the article first, then you can upload a banner image.</p>

      <div v-if="isEditing" style="display: flex; flex-direction: column; gap: var(--ds-space-2)">
        <span class="ds-field-label">Additional images</span>
        <p class="ds-meta">Extra photos shown in a gallery below the article, alongside the lead banner above.</p>
        <div v-if="images.length" style="display: flex; gap: var(--ds-space-2); flex-wrap: wrap">
          <div v-for="image in images" :key="image.id" style="position: relative; width: 140px; height: 90px">
            <img
              :src="image.image_url"
              alt="Article image"
              style="width: 100%; height: 100%; border-radius: var(--ds-radius-md); object-fit: cover"
            />
            <BaseIconButton variant="danger" size="sm" label="Remove this image" style="position: absolute; top: 4px; right: 4px" @click="removeImage(image.id)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18" /><path d="M6 6l12 12" /></svg>
            </BaseIconButton>
          </div>
        </div>
        <BaseFileButton size="sm" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" :disabled="uploadingImage" style="align-self: flex-start" @change="handleAddImageSelect">
          {{ uploadingImage ? 'Uploading…' : 'Add image' }}
        </BaseFileButton>
      </div>

      <label class="ds-field">
        <span class="ds-field-label">Status</span>
        <BaseSelect v-model="form.status" :options="statusOptions" />
        <span v-if="errors.status" class="ds-field-error-text">{{ errors.status }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Category (optional)</span>
        <BaseSelect v-model="form.category" :options="[{ value: '', label: 'None' }, ...categoryOptions]" />
        <span v-if="errors.category" class="ds-field-error-text">{{ errors.category }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Author (optional)</span>
        <span class="ds-field-control"><input v-model="form.author" type="text" class="ds-field-input" placeholder="e.g. Rupa Sengupta" /></span>
        <span v-if="errors.author" class="ds-field-error-text">{{ errors.author }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Publish date (leave blank while drafting)</span>
        <span class="ds-field-control"><input v-model="form.published_at" type="datetime-local" class="ds-field-input" /></span>
        <span v-if="errors.published_at" class="ds-field-error-text">{{ errors.published_at }}</span>
      </label>

      <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton to="/admin/news" variant="ghost">Cancel</BaseButton>
        <BaseButton type="button" class="save-news" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </BaseButton>
      </div>
    </div>
  </div>
</template>
