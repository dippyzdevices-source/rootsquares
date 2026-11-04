<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '../../components/ui/BaseButton.vue'
import BaseLoadingState from '../../components/ui/BaseLoadingState.vue'
import {
  fetchAdminTestimonial,
  createAdminTestimonial,
  updateAdminTestimonial,
  ValidationError,
  type TestimonialPayload,
} from '../../services/adminTestimonialsApi'
import { useToast } from '../../composables/useToast'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const testimonialId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})
const isEditing = computed(() => testimonialId.value !== null)

const loading = ref(isEditing.value)
const saving = ref(false)
const errors = ref<Record<string, string>>({})

const form = ref({
  quote: '',
  author_name: '',
  author_context: '',
  photo_url: '',
  sort_order: '0',
  is_active: true,
})

onMounted(async () => {
  if (testimonialId.value === null) return
  try {
    const testimonial = await fetchAdminTestimonial(testimonialId.value)
    form.value = {
      quote: testimonial.quote,
      author_name: testimonial.author_name,
      author_context: testimonial.author_context ?? '',
      photo_url: testimonial.photo_url ?? '',
      sort_order: String(testimonial.sort_order),
      is_active: testimonial.is_active,
    }
  } catch {
    toast.error('Could not load this testimonial')
  } finally {
    loading.value = false
  }
})

function buildPayload(): TestimonialPayload {
  return {
    quote: form.value.quote,
    author_name: form.value.author_name,
    author_context: form.value.author_context || null,
    photo_url: form.value.photo_url || null,
    sort_order: Number(form.value.sort_order) || 0,
    is_active: form.value.is_active,
  }
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    if (isEditing.value && testimonialId.value !== null) {
      await updateAdminTestimonial(testimonialId.value, buildPayload())
      toast.success('Testimonial updated')
    } else {
      await createAdminTestimonial(buildPayload())
      toast.success('Testimonial created')
    }
    router.push('/admin/testimonials')
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      toast.error('Could not save this testimonial')
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
      <h1 class="ds-display ds-display-s">{{ isEditing ? 'Edit testimonial' : 'New testimonial' }}</h1>
    </div>

    <hr class="ds-section-line" />

    <BaseLoadingState v-if="loading" label="Loading testimonial…" />
    <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <label class="ds-field">
        <span class="ds-field-label">Quote</span>
        <span class="ds-textarea-control">
          <textarea v-model="form.quote" rows="4" class="ds-textarea"></textarea>
        </span>
        <span v-if="errors.quote" class="ds-field-error-text">{{ errors.quote }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Author name</span>
        <span class="ds-field-control"><input v-model="form.author_name" type="text" placeholder="Priya Das" class="ds-field-input" /></span>
        <span v-if="errors.author_name" class="ds-field-error-text">{{ errors.author_name }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Context (optional)</span>
        <span class="ds-field-control"><input v-model="form.author_context" type="text" placeholder="Member since 2020" class="ds-field-input" /></span>
        <span v-if="errors.author_context" class="ds-field-error-text">{{ errors.author_context }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Photo URL (optional)</span>
        <span class="ds-field-control"><input v-model="form.photo_url" type="text" class="ds-field-input" /></span>
        <span v-if="errors.photo_url" class="ds-field-error-text">{{ errors.photo_url }}</span>
      </label>

      <label class="ds-field">
        <span class="ds-field-label">Homepage display order</span>
        <span class="ds-field-control"><input v-model="form.sort_order" type="number" class="ds-field-input" /></span>
        <span class="ds-field-hint">Lower numbers appear first, both here and in the homepage carousel.</span>
        <span v-if="errors.sort_order" class="ds-field-error-text">{{ errors.sort_order }}</span>
      </label>

      <label class="ds-checkbox">
        <input v-model="form.is_active" type="checkbox" />
        <span class="ds-checkbox-box">✓</span>
        <span class="ds-checkbox-label">Active (shown on the homepage)</span>
      </label>

      <div style="display: flex; justify-content: flex-end; gap: var(--ds-space-2)">
        <BaseButton to="/admin/testimonials" variant="ghost">Cancel</BaseButton>
        <BaseButton type="button" class="save-testimonial" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </BaseButton>
      </div>
    </div>
  </div>
</template>
