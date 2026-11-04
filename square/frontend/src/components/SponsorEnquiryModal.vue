<script setup lang="ts">
import { squareProfile } from '../services/squareConfig'
import { ref, watch } from 'vue'
import BaseButton from './ui/BaseButton.vue'
import BaseInput from './ui/BaseInput.vue'
import BaseModal from './ui/BaseModal.vue'
import { ValidationError } from '../services/membershipDriveApi'
import { enquireSponsorship } from '../services/eventSupportApi'

const props = defineProps<{ modelValue: boolean; slug: string; eventTitle: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const empty = () => ({ name: '', contact_name: '', email: '', phone: '', website: '', amount: '', requirements: '' })
const form = ref(empty())
const errors = ref<Record<string, string>>({})
const formError = ref('')
const submitting = ref(false)
const done = ref(false)

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    form.value = empty()
    errors.value = {}
    formError.value = ''
    done.value = false
  },
)

async function submit() {
  errors.value = {}
  formError.value = ''
  const local: Record<string, string> = {}
  if (!form.value.name.trim()) local.name = 'This field is required.'
  if (!form.value.contact_name.trim()) local.contact_name = 'This field is required.'
  if (!form.value.email.trim()) local.email = 'This field is required.'
  if (Object.keys(local).length) {
    errors.value = local
    return
  }
  submitting.value = true
  try {
    await enquireSponsorship(props.slug, {
      name: form.value.name.trim(),
      contact_name: form.value.contact_name.trim(),
      email: form.value.email.trim(),
      phone: form.value.phone.trim() || undefined,
      website: form.value.website.trim() || undefined,
      amount: form.value.amount ? Math.round(Number(form.value.amount) * 100) : undefined,
      requirements: form.value.requirements.trim() || undefined,
    })
    done.value = true
  } catch (err) {
    if (err instanceof ValidationError) errors.value = err.errors
    else formError.value = err instanceof Error ? err.message : 'Could not send your enquiry.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <BaseModal :model-value="modelValue" title="Become a sponsor" @update:model-value="emit('update:modelValue', $event)">
    <div v-if="done" style="display: flex; flex-direction: column; gap: var(--ds-space-4)">
      <p class="ds-body">
        Thank you for offering to sponsor {{ eventTitle }}! We have your details and will contact you to agree the
        sponsorship and how to pay.
      </p>
      <div><BaseButton variant="ghost" @click="emit('update:modelValue', false)">Close</BaseButton></div>
    </div>

    <form v-else style="display: flex; flex-direction: column; gap: var(--ds-space-4)" @submit.prevent="submit">
      <p class="ds-meta">Tell us who you are and what you would like in return; we get back to you to agree the details.</p>

      <div>
        <BaseInput v-model="form.name" label="Company or sponsor name" autocomplete="organization" />
        <span v-if="errors.name" class="ds-field-error-text">{{ errors.name }}</span>
      </div>
      <div>
        <BaseInput v-model="form.contact_name" label="Contact person" autocomplete="name" />
        <span v-if="errors.contact_name" class="ds-field-error-text">{{ errors.contact_name }}</span>
      </div>
      <div>
        <BaseInput v-model="form.email" label="Email" type="email" autocomplete="email" />
        <span v-if="errors.email" class="ds-field-error-text">{{ errors.email }}</span>
      </div>
      <div>
        <BaseInput v-model="form.phone" label="Phone (optional)" type="tel" autocomplete="tel" />
        <span v-if="errors.phone" class="ds-field-error-text">{{ errors.phone }}</span>
      </div>
      <div>
        <BaseInput v-model="form.website" label="Website (optional)" type="url" />
        <span v-if="errors.website" class="ds-field-error-text">{{ errors.website }}</span>
      </div>
      <div>
        <BaseInput v-model="form.amount" :label="`Amount you have in mind, ${squareProfile.currency} (optional)`" type="number" inputmode="decimal" />
        <span v-if="errors.amount" class="ds-field-error-text">{{ errors.amount }}</span>
      </div>
      <label class="ds-field">
        <span class="ds-field-label">Your requirements (optional)</span>
        <span class="ds-textarea-control">
          <textarea v-model="form.requirements" rows="4" class="ds-textarea" placeholder="For example logo placement, a banner, a mention on stage"></textarea>
        </span>
        <span v-if="errors.requirements" class="ds-field-error-text">{{ errors.requirements }}</span>
      </label>

      <div v-if="formError" class="ds-alert ds-alert-danger"><div>{{ formError }}</div></div>

      <BaseButton type="submit" size="lg" full-width :disabled="submitting">{{ submitting ? 'Sending…' : 'Send enquiry' }}</BaseButton>
    </form>
  </BaseModal>
</template>
