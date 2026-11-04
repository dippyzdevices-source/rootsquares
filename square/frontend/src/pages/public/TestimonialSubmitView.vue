<script setup lang="ts">
import { squareProfile } from '../../services/squareConfig'
import { ref } from 'vue'
import BaseButton from '../../components/ui/BaseButton.vue'
import { submitTestimonial, ValidationError } from '../../services/testimonialsApi'

const form = ref({ quote: '', author_name: '', author_context: '', photo_url: '' })
const errors = ref<Record<string, string>>({})
const submitting = ref(false)
const submitted = ref(false)
const formError = ref('')

const QUOTE_MAX = 1000

async function submit() {
  formError.value = ''
  errors.value = {}
  submitting.value = true
  try {
    await submitTestimonial({
      quote: form.value.quote,
      author_name: form.value.author_name,
      author_context: form.value.author_context || null,
      photo_url: form.value.photo_url || null,
    })
    submitted.value = true
  } catch (err) {
    if (err instanceof ValidationError) {
      errors.value = err.errors
    } else {
      formError.value = 'Could not send this right now — please try again shortly.'
    }
  } finally {
    submitting.value = false
  }
}

function shareAnother() {
  submitted.value = false
  formError.value = ''
  errors.value = {}
  form.value = { quote: '', author_name: '', author_context: '', photo_url: '' }
}
</script>

<template>
  <div class="ds-scope">
    <section class="ds-band ds-band-wash" style="padding-bottom: var(--ds-space-6)">
      <div class="ds-container ds-heading">
        <span class="ds-eyebrow"><span class="ds-eyebrow-rule" />Share your story</span>
        <h1 class="ds-display ds-display-m">Tell us what {{ squareProfile.name }} means to you</h1>
        <p class="ds-intro">
          A line about an evening you remember, a class, or what the community has meant to
          your family — we'd love to share it. An admin reviews every submission before it
          appears on the site.
        </p>
      </div>
    </section>

    <section class="ds-band ds-band-paper" style="padding-top: var(--ds-space-6)">
      <div class="ds-container" style="max-width: var(--ds-container-narrow); margin: 0 auto">
        <div v-if="submitted" class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
          <div class="ds-alert ds-alert-success">
            <div style="flex: 1">
              <strong class="ds-alert-title">Thank you — sent for review</strong>
              An admin will take a look before it goes live on the site. We appreciate you sharing it.
            </div>
            <BaseButton type="button" variant="ghost" size="sm" style="flex-shrink: 0" @click="shareAnother">Share another</BaseButton>
          </div>
        </div>

        <div v-else class="ds-card" style="display: flex; flex-direction: column; gap: var(--ds-space-5)">
          <div>
            <h2 class="ds-title">Your testimonial</h2>
            <p class="ds-meta" style="margin-top: var(--ds-space-1)">Your name and story are all we need — everything else is optional.</p>
          </div>

          <div v-if="formError" class="ds-alert ds-alert-danger">
            <div><strong class="ds-alert-title">Not quite ready to send</strong>{{ formError }}</div>
          </div>

          <label class="ds-field">
            <span class="ds-field-label">Your story</span>
            <span class="ds-textarea-control">
              <textarea
                v-model="form.quote"
                rows="5"
                :maxlength="QUOTE_MAX"
                :placeholder="`${squareProfile.name} feels like family…`"
                class="ds-textarea"
              ></textarea>
            </span>
            <span class="ds-textarea-count">{{ form.quote.length }} / {{ QUOTE_MAX }}</span>
            <span v-if="errors.quote" class="ds-field-error-text">{{ errors.quote }}</span>
          </label>

          <div class="ds-cards ds-cards--2" style="display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap: var(--ds-space-4)">
            <label class="ds-field">
              <span class="ds-field-label">Your name</span>
              <span class="ds-field-control"><input v-model="form.author_name" type="text" placeholder="Your full name" class="ds-field-input" /></span>
              <span v-if="errors.author_name" class="ds-field-error-text">{{ errors.author_name }}</span>
            </label>
            <label class="ds-field">
              <span class="ds-field-label">Context (optional)</span>
              <span class="ds-field-control"><input v-model="form.author_context" type="text" placeholder="Member since 2020" class="ds-field-input" /></span>
              <span v-if="errors.author_context" class="ds-field-error-text">{{ errors.author_context }}</span>
              <span class="ds-field-hint">e.g. how long you've been part of {{ squareProfile.name }}</span>
            </label>
          </div>

          <label class="ds-field">
            <span class="ds-field-label">Photo URL (optional)</span>
            <span class="ds-field-control"><input v-model="form.photo_url" type="text" placeholder="https://…" class="ds-field-input" /></span>
            <span v-if="errors.photo_url" class="ds-field-error-text">{{ errors.photo_url }}</span>
          </label>

          <div style="display: flex; gap: var(--ds-space-3); flex-wrap: wrap; align-items: center">
            <BaseButton type="button" size="lg" :disabled="submitting" @click="submit">
              {{ submitting ? 'Sending…' : 'Share my story' }}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></svg>
            </BaseButton>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
